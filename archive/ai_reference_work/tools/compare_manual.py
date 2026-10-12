"""Audit a manual exam schedule against the EMS plan for the same dataset.

    python tools/compare_manual.py data/midterm_2026 out/midterm_2026

Reads ``<dataset>/manual_schedule.csv`` (paper_id, date, session) and the
EMS ``schedule.csv`` + ``slot_summary.csv``, measures both on the same
registrations, and writes ``<out>/manual_vs_ems.md``.

The manual plan has no seating, so its room/invigilator needs are computed
the way EMS would seat it: per slot, papers are split onto the two room sides
as evenly as possible (largest first), and rooms are opened until both sides
fit — the minimum needed so that no two neighbours write the same paper.
"""
from __future__ import annotations

import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ems.geometry import layouts_for  # noqa: E402
from ems.ingest import load_dataset  # noqa: E402
from ems.mapping import build_paper_map  # noqa: E402


def rows(p: Path):
    with p.open(newline="") as fh:
        return list(csv.DictReader(fh))


def measure(slot_of: dict[str, tuple[str, str]], ds, pm, layouts, per_room: int) -> dict:
    sessions = ds.config.sessions
    days = [d.isoformat() for d in ds.config.exam_days()]
    by_slot = defaultdict(list)
    for p, s in slot_of.items():
        by_slot[s].append(p)
    same_day = consecutive = 0
    clash_same_slot = 0
    for sid, papers in pm.student_papers.items():
        ss = [slot_of[p] for p in papers if p in slot_of]
        cnt = Counter(ss)
        if any(v > 1 for v in cnt.values()):
            clash_same_slot += 1
        dd = Counter(d for d, _ in ss)
        if any(v > 1 for v in dd.values()):
            same_day += 1
        idx = sorted({days.index(d) for d in dd})
        if any(b - a == 1 for a, b in zip(idx, idx[1:])):
            consecutive += 1
    side_a = [len(l.side_a) for l in layouts]
    side_b = [len(l.side_b) for l in layouts]
    room_slots, peak_rooms, detail = 0, 0, []
    for s in sorted(by_slot, key=lambda s: (s[0], sessions.index(s[1]))):
        papers = sorted(by_slot[s], key=lambda p: -pm.size(p))
        a = b = 0
        for p in papers:  # greedy balanced partition
            if a <= b:
                a += pm.size(p)
            else:
                b += pm.size(p)
        a, b = max(a, b), min(a, b)
        need, ca, cb = 0, 0, 0
        while (ca < a or cb < b) and need < len(layouts):
            ca += side_a[need]
            cb += side_b[need]
            need += 1
        short = ca < a or cb < b
        if short:  # beyond the room list: extrapolate with the last room's size
            extra = max(math.ceil((a - ca) / side_a[-1]), math.ceil((b - cb) / side_b[-1]), 0)
            need += extra
        room_slots += need
        peak_rooms = max(peak_rooms, need)
        detail.append((s, papers, sum(pm.size(p) for p in papers), need))
    return {"same_slot_clash": clash_same_slot, "same_day": same_day, "consecutive": consecutive,
            "slots": len(by_slot), "room_slots": room_slots, "peak_rooms": peak_rooms,
            "duties": room_slots * per_room, "peak_invigilators": peak_rooms * per_room, "detail": detail}


def main():
    data, out = Path(sys.argv[1]), Path(sys.argv[2])
    ds = load_dataset(data)
    pm = build_paper_map(ds)
    layouts = layouts_for(ds.rooms, ds.config["seating"])
    per_room = int(ds.config["duties"]["invigilators_per_room"])
    manual = {r["paper_id"]: (r["date"], r["session"]) for r in rows(data / "manual_schedule.csv")
              if r["paper_id"] in pm.paper_students}
    ems = {r["paper_id"]: (r["date"], r["session"]) for r in rows(out / "schedule.csv")}
    ems_rooms = sum(int(r["rooms_open"]) for r in rows(out / "slot_summary.csv"))
    ems_peak = max(int(r["rooms_open"]) for r in rows(out / "slot_summary.csv"))
    m = measure(manual, ds, pm, layouts, per_room)
    e = measure(ems, ds, pm, layouts, per_room)
    e["room_slots"], e["peak_rooms"] = ems_rooms, ems_peak  # use what EMS actually opened
    e["duties"], e["peak_invigilators"] = ems_rooms * per_room, ems_peak * per_room
    missing = sorted(set(pm.paper_students) - set(manual))

    def row(label, k):
        return f"| {label} | {m[k]} | {e[k]} |"

    lines = [
        "# Manual mid-term plan vs EMS plan", "",
        f"Dataset: {ds.config.name}. Both plans are measured on the same reconstructed registrations "
        f"({len(pm.student_papers)} students, {sum(pm.size(p) for p in pm.paper_students)} paper-sittings), "
        f"with 30-seat rooms and no two neighbours writing the same paper.", "",
        "| Measure | Manual plan (sheet) | EMS |", "|---|---|---|",
        row("Students with two papers in the same slot", "same_slot_clash"),
        row("Students with two papers on the same day", "same_day"),
        row("Students with papers on consecutive days", "consecutive"),
        row("Slots used", "slots"),
        row("Room-slots needed (neighbours separated)", "room_slots"),
        row("Peak rooms in one slot", "peak_rooms"),
        row("Invigilation duties (2 per room)", "duties"),
        row("Peak invigilators in one slot", "peak_invigilators"),
        "",
    ]
    if missing:
        lines.append(f"Papers with no single slot in the sheet (not counted for the manual plan): "
                     f"{', '.join(missing)}.\n")
    for name, res in (("Manual plan", m), ("EMS plan", e)):
        lines += [f"## {name} by slot", "", "| Slot | Papers | Students | Rooms needed |", "|---|---|---|---|"]
        lines += [f"| {s[0]} {s[1]} | {' '.join(p)} | {n} | {r} |" for s, p, n, r in res["detail"]]
        lines.append("")
    lines += ["(EMS rooms per slot here use the same estimator as the manual plan; the rooms EMS actually "
              "opened are in `slot_summary.csv` and in the table above.)"]
    (out / "manual_vs_ems.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    main()

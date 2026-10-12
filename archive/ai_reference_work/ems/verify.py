"""Independent plan verifier (SRS 3.5 — correctness, defensibility, auditability).

Re-checks every hard rule of SRS 2.4.1 from the *output CSV files* and the
input dataset alone. It shares no state with the solver, so a bug in an
engine cannot hide itself. Also measures the soft rules.

    python -m ems verify out/dummy
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .config import INVIGILATION_ONLY, Config
from .conflicts import build_conflicts
from .geometry import Seat, layouts_for
from .ingest import load_dataset
from .mapping import build_paper_map


def _rows(path: Path):
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def verify_plan(out_dir: str | Path, dataset_dir: str | Path | None = None, pins_file=None) -> dict:
    out = Path(out_dir)
    run = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else {}
    data = Path(dataset_dir or run["dataset"])
    pins_file = pins_file or run.get("pins_file")
    ds = load_dataset(data, pins_file=pins_file)
    if "config" in run:  # the exact (possibly overridden) policy the plan was solved under
        ds.config = Config(run["config"])
    pm = build_paper_map(ds)
    cg = build_conflicts(ds, pm)
    gap = ds.config.min_day_gap
    day_idx = {d.isoformat(): i for i, d in enumerate(ds.config.exam_days())}
    sessions = ds.config.sessions
    per_room = int(ds.config["duties"]["invigilators_per_room"])
    layouts = {l.room.room_id: l for l in layouts_for(ds.rooms, ds.config["seating"])}

    sched = _rows(out / "schedule.csv")
    seating = _rows(out / "seating.csv")
    duties = _rows(out / "duties.csv")
    exempt = set(run.get("coverage_exempt", {}))
    checks = []

    def check(cid, rule, passed, detail):
        checks.append({"id": cid, "rule": rule, "passed": bool(passed), "detail": detail})

    slot_of = {r["paper_id"]: (r["date"], r["session"]) for r in sched}

    # H1 every registration seated exactly once, nothing extra
    want = Counter((s, p) for s, ps in pm.student_papers.items() for p in ps)
    got = Counter((r["student_id"], r["paper_id"]) for r in seating)
    missing = [k for k in want if got[k] == 0]
    dup = [k for k, v in got.items() if v > 1]
    extra = [k for k in got if k not in want]
    check("H1", "Every registered (student, paper) has exactly one seat", not (missing or dup or extra),
          f"{len(want)} sittings expected, {sum(got.values())} seated; missing {len(missing)}, duplicated "
          f"{len(dup)}, unexpected {len(extra)}" + (f"; e.g. {(missing or dup or extra)[0]}" if missing or dup or extra else ""))

    # H2 all offerings of a paper share one slot, which is the scheduled one
    bad = [r for r in seating if slot_of.get(r["paper_id"]) != (r["date"], r["session"])]
    unsched = [p for p in pm.paper_students if p not in slot_of]
    check("H2", "All offerings (course codes) of a paper sit in its one scheduled slot", not bad and not unsched,
          f"{len(bad)} seat(s) outside their paper's slot; {len(unsched)} paper(s) unscheduled; "
          f"{len(pm.shared_papers)} paper(s) have several course codes")

    # H3 day-gap rule per student
    viol = []
    for sid, ps in pm.student_papers.items():
        ds_ = sorted(day_idx[slot_of[p][0]] for p in ps if p in slot_of)
        for a, b in zip(ds_, ds_[1:]):
            if b - a < gap:
                viol.append(sid)
                break
    check("H3", f"No student writes on exam days less than {gap} apart", not viol,
          f"{len(viol)} student(s) violate" + (f", e.g. {viol[0]}" if viol else f"; {len(pm.student_papers)} checked"))

    # H4 seats exist, not double-booked, room capacity
    occ = Counter((r["date"], r["session"], r["room_id"], r["seat"]) for r in seating)
    clash = [k for k, v in occ.items() if v > 1]
    bad_seat = []
    for r in seating:
        lay = layouts.get(r["room_id"])
        if lay is None or Seat(int(r["row"]) - 1, int(r["col"]) - 1) not in lay.neighbours:
            bad_seat.append(r)
    check("H4", "Each seat exists and holds at most one student per slot", not clash and not bad_seat,
          f"{len(clash)} double-booked seat(s), {len(bad_seat)} nonexistent seat(s)")

    # H5 adjacency
    grid = {}
    for r in seating:
        grid[(r["date"], r["session"], r["room_id"], Seat(int(r["row"]) - 1, int(r["col"]) - 1))] = r["paper_id"]
    adj_viol = []
    for (d, s, room, seat), p in grid.items():
        for nb in layouts[room].neighbours[seat]:
            if grid.get((d, s, room, nb)) == p:
                adj_viol.append((d, s, room, seat.label, nb.label, p))
    sc = ds.config["seating"]
    check("H5", "No two adjacent students write the same paper", not adj_viol,
          f"{len(adj_viol) // 2} adjacent same-paper pair(s); adjacency = same bench"
          f"{' + across aisle' if sc['across_aisle_adjacent'] else ''}{' + front/back' if sc['front_back_adjacent'] else ''}")

    # H6 roll order: each paper's roster laid down in roll order (rooms in priority order)
    prio = {r.room_id: i for i, r in enumerate(ds.rooms)}
    order_bad = []
    by_paper = defaultdict(list)
    for r in seating:
        lay = layouts[r["room_id"]]
        seat = Seat(int(r["row"]) - 1, int(r["col"]) - 1)
        side = lay.side_a if seat in set(lay.side_a) else lay.side_b
        by_paper[r["paper_id"]].append(((prio[r["room_id"]], side.index(seat)), r["student_id"]))
    for p, v in by_paper.items():
        rolls = [sid for _, sid in sorted(v)]
        if rolls != sorted(rolls):
            order_bad.append(p)
    check("H6", "Each paper's roster is distributed in roll order across stripes", not order_bad,
          f"{len(order_bad)} paper(s) out of roll order" + (f": {', '.join(order_bad[:5])}" if order_bad else ""))

    # Duties
    open_rooms = {(r["date"], r["session"], r["room_id"]) for r in seating}
    staff = defaultdict(list)
    for d in duties:
        staff[(d["date"], d["session"], d["room_id"])].append(d["teacher_id"])
    wrong = [k for k in open_rooms if len(staff.get(k, [])) != per_room]
    ghost = [k for k in staff if k not in open_rooms]
    check("H7", f"Exactly {per_room} invigilators per open room per slot", not wrong and not ghost,
          f"{len(open_rooms)} open room-slot(s); {len(wrong)} wrongly staffed; {len(ghost)} duty(ies) in empty rooms")

    per_slot = Counter((d["teacher_id"], d["date"], d["session"]) for d in duties)
    double = [k for k, v in per_slot.items() if v > 1]
    check("H8", "At most one duty per teacher per slot", not double, f"{len(double)} clash(es)")

    content = defaultdict(set)
    for r in seating:
        content[(r["date"], r["session"], r["room_id"])].add((r["paper_id"], r["section_id"]))
    taught = defaultdict(set)
    for t, p, sec in cg.taught:
        taught[t].add((p, sec))
    excl = [(d["teacher_id"], d["room_id"], d["date"], d["session"]) for d in duties
            if taught[d["teacher_id"]] & content[(d["date"], d["session"], d["room_id"])]]
    check("H9", "No teacher invigilates a room holding a student they taught for the paper written there",
          not excl, f"{len(excl)} violation(s)" + (f", e.g. {excl[0]}" if excl else ""))

    if ds.config["duties"]["require_own_paper_duty"]:
        papers_in = {k: {p for p, _ in v} for k, v in content.items()}
        covered = {d["teacher_id"] for d in duties
                   if papers_in.get((d["date"], d["session"], d["room_id"]), set()) & cg.teacher_papers.get(d["teacher_id"], set())}
        need = [t for t in cg.teacher_papers if ds.teachers[t].rank not in INVIGILATION_ONLY and t not in exempt]
        uncovered = [t for t in need if t not in covered]
        check("H10", "Each teaching staff member has ≥ 1 duty on a paper they teach (PhD scholars / staff exempt)",
              not uncovered, f"{len(need) - len(uncovered)}/{len(need)} covered; {len(exempt)} exempt "
                             f"(impossible by data)" + (f"; uncovered: {', '.join(uncovered[:8])}" if uncovered else ""))

    pin_bad = []
    for pin in ds.pins:
        if pin.kind == "paper_slot" and slot_of.get(pin.paper_id) != (pin.date, pin.session):
            pin_bad.append(pin.describe())
        if pin.kind == "teacher_room" and pin.teacher_id not in staff.get((pin.date, pin.session, pin.room_id), []):
            pin_bad.append(pin.describe())
    check("H11", "Every pinned override is honoured", not pin_bad,
          f"{len(ds.pins)} pin(s); " + ("all honoured" if not pin_bad else "broken: " + "; ".join(pin_bad)))

    # --- soft measures -------------------------------------------------------
    cap_soft = int(ds.config["seating"]["max_papers_per_room_soft"])
    ppr = {k: len({p for p, _ in v}) for k, v in content.items()}
    per_day = Counter((d["teacher_id"], d["date"]) for d in duties)
    loads = Counter(d["teacher_id"] for d in duties)
    w = ds.config["duties"]["rank_weights"]
    wl = {t: loads[t] / w[ds.teachers[t].rank] for t in ds.teachers}
    dept = {t: ds.teachers[t].department for t in ds.teachers}
    room_dom = {k: {ds.papers[p].department for p, _ in v} for k, v in content.items()}
    mixed = sum(1 for k, ts in staff.items() if per_room == 2 and k in room_dom
                and sum(dept[t] in room_dom[k] for t in ts) == 1)
    student_days = defaultdict(list)
    for sid, ps in pm.student_papers.items():
        student_days[sid] = sorted(day_idx[slot_of[p][0]] for p in ps if p in slot_of)
    gaps = [b - a for v in student_days.values() for a, b in zip(v, v[1:])]
    used_days = sorted({day_idx[d] for d, _ in slot_of.values()})
    soft = {
        "Exam span": f"{used_days[-1] - used_days[0] + 1 if used_days else 0} exam day(s) "
                     f"({min(slot_of.values())[0] if slot_of else '-'} → {max(slot_of.values())[0] if slot_of else '-'})",
        "Shortest gap between a student's exams": f"{min(gaps) if gaps else '-'} exam day(s)",
        "Max distinct papers in one room": f"{max(ppr.values()) if ppr else 0} (soft cap {cap_soft}; "
                                           f"{sum(1 for v in ppr.values() if v > cap_soft)} room-slot(s) over)",
        "Teacher-days with more than one duty": str(sum(1 for v in per_day.values() if v > 1)),
        "Rooms with one in-domain + one out-of-domain invigilator": f"{mixed} of {len(staff)}",
        "Weighted duty load (duties ÷ rank weight)": (f"min {min(wl.values()):.1f}, max {max(wl.values()):.1f}"
                                                      if wl else "-"),
    }
    result = {"all_passed": all(c["passed"] for c in checks), "hard": checks, "soft": soft}
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def format_verification(v: dict) -> str:
    lines = [f"Verification: {'ALL HARD RULES PASS' if v['all_passed'] else 'FAILURES FOUND'}"]
    for c in v["hard"]:
        lines.append(f"  {'PASS' if c['passed'] else 'FAIL'}  {c['id']:<4} {c['rule']} — {c['detail']}")
    lines.append("  Soft measures:")
    lines += [f"    · {k}: {val}" for k, val in v["soft"].items()]
    return "\n".join(lines)


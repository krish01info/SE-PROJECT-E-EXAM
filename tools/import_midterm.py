"""Import the real Mid-Term (March 2026) master sheet into an EMS dataset.

    python tools/import_midterm.py data/raw/Mid_Term_Data_March_2026.csv

The sheet is a course list, not a registration system: it has per-course
student counts and, per section column (CSE1–CSE8, ME, ECOMP), the teacher
who teaches it. It has no roll numbers. This importer therefore
*reconstructs* a dataset, and writes every assumption it makes to
``import_report.md`` next to the output:

* Cohort = batch year (2025 → 1st year, 2024 → 2nd, 2023 → 3rd).
* A section takes a course if its column names a teacher (not blank / NA /
  "Course completed in Ist sem").
* Section size = the largest per-section share any course demands of it,
  so every course's student count fits into its offering sections.
* Registrations: n students sampled (seeded) from the offering sections.
  Same-cohort courses that the manual plan put in the *same slot* are
  treated as alternative electives (no student takes both).
* MEC1101 (practical in GA 102 over two days) and CSE2021 (lab exam run by
  the coordinator) are excluded, as the sheet's own discussion decided.
* FIN1001 (multidisciplinary) takers are drawn from the 2024 batch.
* Rank is unknown: "Prof." → professor, everyone else → assistant.
  Invigilation-only staff named in the Invigilators column get rank "staff".
* Rooms are not in the sheet: 36 assumed rooms of 30 seats (the sheet's
  stated room size). Replace rooms.csv with the real inventory.

Names are pseudonymised (F001…, S01…). The name map is written outside the
dataset (default data/raw/), which is git-ignored — keep it private.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import random
import re
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

SECTION_COLS = ["CSE1", "CSE2", "CSE3", "CSE4", "CSE5", "CSE6", "CSE7", "CSE8", "ME", "ECOMP"]
SHORT = {"ME": "ME", "ECOMP": "EC"}
COHORT = {"2025": "Y1-2025", "2024": "Y2-2024", "2023": "Y3-2023"}
EXCLUDE = {
    "MEC1101": "practical exam in GA 102 over Thu/Fri with no student count — scheduled outside the written-exam plan",
    "CSE2021": "lab-based exam; coordinator runs it in NB labs on Tuesday (sheet discussion item 3)",
}
MDC_COHORT = "Y2-2024"
DEPT = {"MTH": "MATH", "CSE": "CSE", "ECE": "ECE", "MEC": "MECH", "PRJ": "ENGG", "PSP": "HUM", "SKL": "SKILLS",
        "FIN": "MGMT"}
WEEK = {"Monday": date(2026, 3, 23), "Tuesday": date(2026, 3, 24), "Wednesday": date(2026, 3, 25),
        "Thursday": date(2026, 3, 26), "Friday": date(2026, 3, 27)}


def norm(name: str) -> str:
    n = re.sub(r"\(.*?\)", " ", name)
    n = re.sub(r"-\s*(lecture|discussion|lab)\b", " ", n, flags=re.I)
    n = re.sub(r"\b(dr|prof|mr|ms|mrs)\b\.?", " ", n, flags=re.I)
    n = n.replace(".", " ")
    return re.sub(r"\s+", " ", n).strip().lower()


def clean(raw: str) -> str:
    s = re.sub(r"\(.*?\)", "", raw)
    s = re.sub(r"\s*-\s*(lecture|discussion|lab)\b", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def split_names(cell: str) -> list[str]:
    parts = re.split(r"[/&]", cell)
    return [p.strip() for p in parts if norm(p)]


def valid(cell: str) -> bool:
    c = (cell or "").strip()
    return bool(c) and c not in ("NA", "`") and not c.lower().startswith("course completed")


class People:
    def __init__(self):
        self.ids: dict[str, str] = {}  # normalised name -> id
        self.display: dict[str, str] = {}
        self.rank: dict[str, str] = {}
        self.dept: dict[str, str] = {}
        self.nf = self.ns = 0

    def match(self, raw: str) -> str | None:
        n = norm(raw)
        if n in self.ids:
            return self.ids[n]
        close = difflib.get_close_matches(n, list(self.ids), n=1, cutoff=0.88)
        return self.ids[close[0]] if close else None

    def faculty(self, raw: str, dept: str) -> str:
        tid = self.match(raw)
        n = norm(raw)
        if not tid and " " not in n:  # "Dr. Hirdesh" -> the one faculty member called Hirdesh
            hits = [t for t in self.display if t.startswith("F") and norm(self.display[t]).split()[0] == n]
            tid = hits[0] if len(hits) == 1 else None
        if tid:
            if "prof." in raw.lower() and self.rank[tid] != "professor":
                self.rank[tid] = "professor"
            return tid
        self.nf += 1
        tid = f"F{self.nf:03d}"
        self.ids[norm(raw)] = tid
        self.display[tid] = clean(raw)
        self.rank[tid] = "professor" if re.search(r"\bprof\b", raw, re.I) else "assistant"
        self.dept[tid] = dept
        return tid

    def invigilator(self, raw: str, row_teachers: set[str]) -> str:
        tid = self.match(raw)
        if tid:
            return tid
        n = norm(raw)
        if " " not in n:  # a bare first name: same person if they teach this course
            hits = [t for t in row_teachers if norm(self.display[t]).split()[0] == n]
            if len(hits) == 1:
                return hits[0]
        self.ns += 1
        tid = f"S{self.ns:02d}"
        self.ids[n] = tid
        self.display[tid] = raw.strip()
        self.rank[tid] = "staff"
        self.dept[tid] = "ADMIN"
        return tid


def parse_slot(r) -> tuple[str, str] | None:
    m, a = r["Morning"].strip(), r["Afternoon"].strip()
    sess = "Morning" if m else "Afternoon" if a else None
    day = m or a
    if not sess or "/" in day:
        return None
    if r["Date"].strip():
        dt = re.match(r"(\d+) March 2026", r["Date"].strip())
        d = date(2026, 3, int(dt.group(1))) if dt else WEEK.get(day)
    else:
        d = WEEK.get(day)
    return (d.isoformat(), sess) if d else None


def build(sheet: Path, out: Path, name_map: Path, seed: int = 2026, rooms: int = 36, extra: int = 20):
    rng = random.Random(seed)
    with sheet.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("Course Code", "").strip()]
    people = People()
    report = []
    courses = []  # dicts
    for r in rows:
        code = r["Course Code"].strip()
        dept = DEPT.get(code[:3], "GEN")
        c = {"code": code, "title": r["Course"].strip(), "year": r["Year"].strip(), "dept": dept,
             "n": int(r["No. of Students"]) if r["No. of Students"].strip().isdigit() else None,
             "sections": {}, "manual": parse_slot(r), "invig": r["Invigilators"]}
        if code in EXCLUDE:
            report.append(f"* **{code} {c['title']}** excluded — {EXCLUDE[code]}.")
            continue
        for col in SECTION_COLS:
            if valid(r[col]):
                c["sections"][col] = [people.faculty(n, dept) for n in split_names(r[col])]
        coord = r["Course Coordinator"].strip()
        if coord:
            c["coordinator"] = [people.faculty(n, dept) for n in split_names(coord)]
        courses.append(c)

    # invigilation-only staff from the Invigilators column
    for c in courses:
        row_t = {t for ts in c["sections"].values() for t in ts}
        for tok in re.split(r"[,+\n]", c["invig"] or ""):
            tok = tok.strip()
            if not tok or "outside" in tok.lower() or not re.search(r"[A-Za-z]", tok):
                continue
            people.invigilator(tok, row_t)

    # cohorts and sections
    sec_size: dict[tuple[str, str], int] = {}
    for c in courses:
        if c["year"] not in COHORT or not c["sections"] or c["n"] is None:
            continue
        share = math.ceil(c["n"] / len(c["sections"]))
        for col in c["sections"]:
            k = (COHORT[c["year"]], col)
            sec_size[k] = max(sec_size.get(k, 0), share)
    for c in courses:  # sections offered only by count-less courses
        if c["year"] in COHORT:
            for col in c["sections"]:
                sec_size.setdefault((COHORT[c["year"]], col), 30)
    sections, roster = [], {}
    for (cohort, col), size in sorted(sec_size.items()):
        sid = f"{cohort[3:]}-{col}"
        yy = cohort[5:]
        short = SHORT.get(col, "C" + col[3:])
        sections.append((sid, cohort))
        roster[sid] = [f"{yy}{short}{i:03d}" for i in range(1, size + 1)]
    sec_id = {(cohort, col): f"{cohort[3:]}-{col}" for (cohort, col) in sec_size}

    # registrations
    papers, codes, regs, teaching = [], [], [], []
    exclusive: dict[str, set[str]] = defaultdict(set)  # course -> courses it can't share students with
    for a in courses:
        for b in courses:
            if a is not b and a["year"] == b["year"] and a["manual"] and a["manual"] == b["manual"]:
                exclusive[a["code"]].add(b["code"])
    taken: dict[str, set[str]] = defaultdict(set)  # student -> courses
    recon = []
    for c in sorted(courses, key=lambda c: -(c["n"] or 0)):
        code = c["code"]
        papers.append((code, c["title"], c["dept"]))
        if c["year"] == "MDC":
            cohort = MDC_COHORT
            pool = [s for sid, co in sections if co == cohort for s in roster[sid]]
            report.append(f"* **{code} {c['title']}** is multidisciplinary; its {c['n']} takers are drawn from "
                          f"{cohort} (assumption).")
        else:
            cohort = COHORT[c["year"]]
            pool = [s for col in c["sections"] for s in roster[sec_id[(cohort, col)]]]
        codes.append((code, code, cohort))
        blocked = exclusive[code]
        eligible = [s for s in pool if not (taken[s] & blocked)]
        want = c["n"] if c["n"] is not None else len(eligible)
        if want > len(eligible):
            recon.append((code, c["n"], len(eligible), "capped: not enough eligible students in offering sections"))
            want = len(eligible)
        # proportional sampling per section keeps it realistic and seeded
        chosen = sorted(eligible) if want == len(eligible) else sorted(rng.sample(eligible, want))
        for s in chosen:
            regs.append((s, code))
            taken[s].add(code)
        recon.append((code, c["n"], len(chosen), "count missing in sheet: all students of offering sections"
                      if c["n"] is None else "ok" if len(chosen) == c["n"] else ""))
        for col, ts in c["sections"].items():
            if c["year"] == "MDC":
                continue
            for t in ts:
                teaching.append((t, code, sec_id[(cohort, col)]))
        if c["year"] == "MDC":
            for t in c.get("coordinator", []):
                for sid in sorted({sid for sid, co in sections if co == cohort}):
                    if any(s in roster[sid] for s in chosen):
                        teaching.append((t, code, sid))

    teachers = [(t, people.rank[t], people.dept[t]) for t in sorted(people.display)]
    teachers += [(f"X{i:02d}", "staff", "EXTERNAL") for i in range(1, extra + 1)]
    # drop reconstructed students who ended up with no paper (over-estimated sections)
    registered = {s for s, _ in regs}
    dropped = sum(1 for ids in roster.values() for s in ids if s not in registered)
    roster = {sid: [s for s in ids if s in registered] for sid, ids in roster.items()}
    room_rows = [(f"R{i:02d}", "assumed", 3, 5, 2, i) for i in range(1, rooms + 1)]
    manual = [(c["code"], c["manual"][0], c["manual"][1]) for c in courses if c["manual"]]

    # --- write ---------------------------------------------------------------
    if out.exists():
        shutil.rmtree(out)
    (out / "students").mkdir(parents=True)

    def w(name, header, data):
        with (out / name).open("w", newline="") as fh:
            cw = csv.writer(fh)
            cw.writerow(header)
            cw.writerows(data)

    w("sections.csv", ["section_id", "cohort_id"], sections)
    for sid, ids in roster.items():
        w(f"students/{sid}.csv", ["student_id"], [[i] for i in ids])
    w("teachers.csv", ["teacher_id", "rank", "department"], teachers)
    w("papers.csv", ["paper_id", "title", "department"], sorted(papers))
    w("course_codes.csv", ["course_code", "paper_id", "cohort_id"], sorted(codes))
    w("registrations.csv", ["student_id", "course_code"], sorted(regs))
    w("teaching.csv", ["teacher_id", "course_code", "section_id"], sorted(set(teaching)))
    w("rooms.csv", ["room_id", "building", "bench_cols", "rows", "seats_per_bench", "priority"], room_rows)
    w("manual_schedule.csv", ["paper_id", "date", "session"], sorted(manual))
    config = {
        "name": "Mid-term exams, March 2026 (reconstructed from the master sheet)",
        "calendar": {"start": "2026-03-23", "end": "2026-03-27", "weekdays": [0, 1, 2, 3, 4], "holidays": [],
                     "sessions": ["Morning", "Afternoon"]},
        "scheduling": {"min_day_gap": 1, "time_limit_s": 60},
        "seating": {"front_back_adjacent": True, "across_aisle_adjacent": True, "max_papers_per_room_soft": 4},
        "duties": {"invigilators_per_room": 2, "require_own_paper_duty": True, "time_limit_s": 90,
                   "rank_weights": {"professor": 0.7, "associate": 0.85, "assistant": 1.0, "phd": 0.5,
                                    "staff": 0.5}},
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    name_map.parent.mkdir(parents=True, exist_ok=True)
    with name_map.open("w", newline="") as fh:
        cw = csv.writer(fh)
        cw.writerow(["id", "name_as_in_sheet", "rank_assumed"])
        cw.writerows(sorted((t, people.display[t], people.rank[t]) for t in people.display))

    n_students = sum(len(v) for v in roster.values())
    lines = [
        "# Import report — Mid-term March 2026 master sheet", "",
        "This dataset is **reconstructed**. The sheet lists courses, per-section teachers and per-course "
        "student counts but no roll numbers, so rosters and registrations are synthesised as described in "
        "`tools/import_midterm.py`. Treat results as a realistic case study, not as the official plan.", "",
        f"* {len(sections)} sections in {len({c for _, c in sections})} cohorts, {n_students} students",
        f"* {len(papers)} papers, {len(regs)} registrations",
        f"* {people.nf} faculty and {people.ns} invigilation-only staff named in the sheet (pseudonymised; name map "
        f"kept outside the dataset), plus **{extra} outside invigilators** (X01…) — the sheet itself relies on "
        f"\"+6 from outside\" / \"+3 from outside\", and the named people alone can staff only ~24 rooms. "
        f"Re-import with `--extra-invigilators 0` to see `ems check` report that shortfall",
        f"* {dropped} reconstructed student(s) received no paper and were dropped",
        f"* {rooms} assumed rooms of 30 seats (3 bench columns × 5 rows × 2 seats) — **replace rooms.csv with "
        f"the real room list**",
        "* Calendar 23–27 March 2026, Morning/Afternoon. `min_day_gap` = 1 (no student sits two papers on one "
        "day). The project's default rule (gap 2) cannot fit this 5-day window; `ems check` shows why.", "",
        "## Decisions taken", "", *report,
        "* Same-cohort courses the manual plan put in one slot are treated as alternative electives: "
        + "; ".join(sorted({" / ".join(sorted({k, *v})) for k, v in exclusive.items() if v})) + ".", "",
        "## Section sizes (estimated)", "",
        "| Section | Cohort | Students |", "|---|---|---|",
        *[f"| {sid} | {co} | {len(roster[sid])} |" for sid, co in sections], "",
        "## Course counts: sheet vs reconstructed", "",
        "| Course | Sheet | Reconstructed | Note |", "|---|---|---|---|",
        *[f"| {c} | {s if s is not None else '—'} | {g} | {n} |" for c, s, g, n in sorted(recon)],
    ]
    (out / "import_report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {out}: {n_students} students in {len(sections)} sections, {len(papers)} papers, "
          f"{len(regs)} registrations, {people.nf} faculty + {people.ns} staff, {rooms} rooms")
    print(f"name map (private): {name_map}")


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", type=Path)
    ap.add_argument("--out", type=Path, default=root / "data" / "midterm_2026")
    ap.add_argument("--name-map", type=Path, default=root / "data" / "raw" / "midterm_2026_name_map.csv")
    ap.add_argument("--rooms", type=int, default=36)
    ap.add_argument("--extra-invigilators", type=int, default=20)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    build(a.sheet, a.out, a.name_map, a.seed, a.rooms, a.extra_invigilators)


if __name__ == "__main__":
    main()

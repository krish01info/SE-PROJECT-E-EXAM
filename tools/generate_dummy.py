"""Generate the Phase 0 dummy dataset (Plan §9.3–9.6).

    python tools/generate_dummy.py                      # -> data/dummy
    python tools/generate_dummy.py --variant realistic  # -> data/dummy_realistic

``base`` is exactly the dataset described in the plan: 1200 students in four
cohorts, 31 papers, 57 teachers (45 teaching + 12 PhD), 40 rooms, March 2026.

``realistic`` closes the gaps the plan lists in §11.2 so they are tested too:
  * the same paper under two course codes (Discrete Mathematics is also
    offered to 3rd-year repeat students under MTH3011);
  * repeat students whose papers do not follow from their cohort;
  * an open course crossing cohorts (Design Thinking also taken by 40 BTech
    2nd-year students under code DES2001B).
Parameters can be changed to stress-test the solver.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from pathlib import Path

COHORTS = {  # cohort: (roll prefix, sections, students)
    "BT2": ("24BTC", 9, 450),
    "BT3": ("23BTC", 9, 450),
    "BB2": ("24BBA", 3, 150),
    "BB3": ("23BBA", 3, 150),
}

# paper_id: (title, department, cohort, kind, course_code)
PAPERS = {
    "DSA": ("Data Structures & Algorithms", "CSE", "BT2", "core", "CSE2001"),
    "OOPS": ("Object Oriented Programming", "CSE", "BT2", "core", "CSE2002"),
    "LA": ("Linear Algebra", "MATH", "BT2", "core", "MTH2001"),
    "DAP": ("Data Analysis in Python", "CSE", "BT2", "core", "CSE2003"),
    "OS": ("Operating Systems", "CSE", "BT2", "core", "CSE2004"),
    "DLD": ("Digital Logic Design", "ECE", "BT2", "core", "ECE2001"),
    "SPHY": ("Semiconductor Physics", "PHY", "BT2", "elective", "PHY2001"),
    "QM": ("Quantum Mechanics", "PHY", "BT2", "elective", "PHY2002"),
    "DM": ("Discrete Mathematics", "MATH", "BT2", "elective", "MTH2002"),
    "ML": ("Machine Learning", "CSE", "BT3", "core", "CSE3001"),
    "AI": ("Artificial Intelligence", "CSE", "BT3", "core", "CSE3002"),
    "SE": ("Software Engineering", "CSE", "BT3", "core", "CSE3003"),
    "COA": ("Computer Architecture & Organization", "CSE", "BT3", "core", "CSE3004"),
    "IOT": ("Internet of Things", "ECE", "BT3", "core", "ECE3001"),
    "CODE": ("Coding Skills", "CSE", "BT3", "core", "CSE3005"),
    "ADS": ("Advanced Data Science", "CSE", "BT3", "elective", "CSE3011"),
    "BDA": ("Big Data Analysis", "CSE", "BT3", "elective", "CSE3012"),
    "CYS": ("Cyber Security", "CSE", "BT3", "elective", "CSE3013"),
    "MACRO": ("Macroeconomics", "MGMT", "BB2", "core", "BBA2001"),
    "BSTAT": ("Business Statistics", "MGMT", "BB2", "core", "BBA2002"),
    "BCOM": ("Business Communication", "MGMT", "BB2", "core", "BBA2003"),
    "FIN": ("Finance", "MGMT", "BB2", "elective", "BBA2011"),
    "MKT": ("Marketing", "MGMT", "BB2", "elective", "BBA2012"),
    "DT": ("Design Thinking", "DESIGN", "BB2", "elective", "DES2001"),
    "BLAW": ("Business Law", "MGMT", "BB3", "core", "BBA3001"),
    "STRAT": ("Strategic Management", "MGMT", "BB3", "core", "BBA3002"),
    "OPM": ("Operations Management", "MGMT", "BB3", "core", "BBA3003"),
    "HAPPY": ("Happiness", "HUM", "BB3", "core", "HUM3001"),
    "BITM": ("Bringing Ideas to Market", "MGMT", "BB3", "elective", "BBA3011"),
    "EIB": ("Ethics & Integrity in Business", "MGMT", "BB3", "elective", "BBA3012"),
    "OB": ("Organizational Behaviour", "MGMT", "BB3", "elective", "BBA3013"),
}
ELECTIVE_SPLIT = {  # deliberate skew (Plan §9.4)
    "BT2": {"DM": 250, "SPHY": 100, "QM": 100},
    "BT3": {"ADS": 240, "BDA": 105, "CYS": 105},
    "BB2": {"FIN": 55, "MKT": 55, "DT": 40},
    "BB3": {"BITM": 50, "EIB": 50, "OB": 50},  # balanced control case
}
SHARED_POOLS = [("DSA", "CODE"), ("OS", "COA"), ("DLD", "IOT"), ("DAP", "ML")]  # Plan §9.5


def section_ids(cohort):
    return [f"{cohort}-S{i:02d}" for i in range(1, COHORTS[cohort][1] + 1)]


def core_units(paper):
    """Teaching units: groups of ≤3 sections taught by one teacher."""
    secs = section_ids(PAPERS[paper][2])
    if len(secs) == 9:
        return [tuple(secs[i:i + 3]) for i in (0, 3, 6)]
    return [tuple(secs[:2]), tuple(secs[2:])]


def build(variant: str, seed: int) -> dict:
    rng = random.Random(seed)
    sections, rosters, regs = [], {}, []
    elective_of = {}
    for cohort, (prefix, n_sec, n_stu) in COHORTS.items():
        per = n_stu // n_sec
        ids = [f"{prefix}{i:04d}" for i in range(1, n_stu + 1)]
        for k, sec in enumerate(section_ids(cohort)):
            sections.append((sec, cohort))
            rosters[sec] = ids[k * per:(k + 1) * per]
        # electives: shuffled assignment honouring the skewed counts
        pool = ids[:]
        rng.shuffle(pool)
        i = 0
        for paper, count in ELECTIVE_SPLIT[cohort].items():
            for sid in pool[i:i + count]:
                elective_of[sid] = paper
            i += count
        for sid in ids:
            for p, (_, _, c, kind, code) in PAPERS.items():
                if c == cohort and kind == "core":
                    regs.append((sid, code))
            regs.append((sid, PAPERS[elective_of[sid]][4]))

    papers = [(p, v[0], v[1]) for p, v in PAPERS.items()]
    codes = [(v[4], p, v[2]) for p, v in PAPERS.items()]

    # --- teaching assignments ------------------------------------------------
    units = []  # (paper, sections)
    sec_of = {sid: sec for sec, ids in rosters.items() for sid in ids}
    for p, v in PAPERS.items():
        if v[3] == "core":
            units += [(p, u) for u in core_units(p)]
        else:
            secs = sorted({sec_of[s] for s, e in elective_of.items() if e == p})
            if ELECTIVE_SPLIT[v[2]][p] > 150:  # big electives get two teachers
                half = len(secs) // 2
                units += [(p, tuple(secs[:half])), (p, tuple(secs[half:]))]
            else:
                units.append((p, tuple(secs)))
    remaining = units[:]
    teacher_units: list[list[tuple]] = []
    for a, b in SHARED_POOLS:  # 12 teachers spanning two cohorts
        ua = [u for u in remaining if u[0] == a]
        ub = [u for u in remaining if u[0] == b]
        for x, y in zip(ua, ub):
            teacher_units.append([x, y])
            remaining.remove(x)
            remaining.remove(y)
    bt = [u for u in remaining if PAPERS[u[0]][2].startswith("BT")]
    bb = [u for u in remaining if PAPERS[u[0]][2].startswith("BB")]
    teacher_units += [[u] for u in bt]
    bb_el = [u for u in bb if PAPERS[u[0]][3] == "elective"]
    bb_core = [u for u in bb if PAPERS[u[0]][3] == "core"]
    for u in bb_el:  # elective teacher also takes a core unit of the same cohort
        partner = next(c for c in bb_core if PAPERS[c[0]][2] == PAPERS[u[0]][2])
        bb_core.remove(partner)
        teacher_units.append([u, partner])
    b2 = next(c for c in bb_core if PAPERS[c[0]][2] == "BB2")
    b3 = next(c for c in bb_core if PAPERS[c[0]][2] == "BB3")
    bb_core.remove(b2)
    bb_core.remove(b3)
    teacher_units.append([b2, b3])
    teacher_units += [[u] for u in bb_core]
    assert len(teacher_units) == 45, len(teacher_units)

    ranks = ["professor"] * 8 + ["associate"] * 12 + ["assistant"] * 25
    rng.shuffle(ranks)
    teachers, teaching = [], []
    for i, tu in enumerate(teacher_units, start=1):
        tid = f"T{i:03d}"
        teachers.append((tid, ranks[i - 1], PAPERS[tu[0][0]][1]))
        for p, secs in tu:
            teaching += [(tid, PAPERS[p][4], s) for s in secs]
    phd_depts = ["CSE"] * 6 + ["MGMT"] * 3 + ["MATH", "PHY", "ECE"]
    teachers += [(f"PHD{i:02d}", "phd", phd_depts[i - 1]) for i in range(1, 13)]

    # --- variant: close the §11.2 gaps ----------------------------------------
    if variant == "realistic":
        codes.append(("MTH3011", "DM", "BT3"))  # same paper, another code + cohort
        bt3 = [sid for sec in section_ids("BT3") for sid in rosters[sec]]
        for sid in rng.sample(bt3, 30):  # repeat students
            regs.append((sid, "MTH3011"))
        codes.append(("DES2001B", "DT", "BT2"))  # open course across cohorts
        dt_teacher = next(t for t, c, _ in teaching if c == "DES2001")
        bt2 = [sid for sec in section_ids("BT2") for sid in rosters[sec]]
        takers = rng.sample(bt2, 40)
        for sid in takers:
            regs.append((sid, "DES2001B"))
        for sec in sorted({sec_of[s] for s in takers}):
            teaching.append((dt_teacher, "DES2001B", sec))

    rooms = [(f"M{i:02d}", "NB", 3, 7, 2, i - 1) for i in range(1, 21)]
    rooms += [(f"S{i:02d}", "NB", 3, 6, 1, 19 + i) for i in range(1, 21)]

    config = {
        "name": "Dummy dataset — Phase 0 §9" + (" (realistic variant)" if variant == "realistic" else ""),
        "calendar": {"start": "2026-03-02", "end": "2026-03-27", "weekdays": [0, 1, 2, 3, 4],
                     "holidays": [], "sessions": ["Morning", "Evening"]},
        "scheduling": {"min_day_gap": 2, "time_limit_s": 60},
        "seating": {"front_back_adjacent": True, "across_aisle_adjacent": True, "max_papers_per_room_soft": 4},
        "duties": {"invigilators_per_room": 2, "require_own_paper_duty": True, "time_limit_s": 120},
    }
    return dict(sections=sections, rosters=rosters, regs=regs, papers=papers, codes=codes,
                teachers=teachers, teaching=teaching, rooms=rooms, config=config)


def write(data: dict, out: Path):
    if out.exists():
        shutil.rmtree(out)
    (out / "students").mkdir(parents=True)

    def w(name, header, rows):
        with (out / name).open("w", newline="") as fh:
            cw = csv.writer(fh)
            cw.writerow(header)
            cw.writerows(rows)

    w("sections.csv", ["section_id", "cohort_id"], data["sections"])
    for sec, ids in data["rosters"].items():
        w(f"students/{sec}.csv", ["student_id"], [[i] for i in ids])
    w("teachers.csv", ["teacher_id", "rank", "department"], data["teachers"])
    w("papers.csv", ["paper_id", "title", "department"], data["papers"])
    w("course_codes.csv", ["course_code", "paper_id", "cohort_id"], data["codes"])
    w("registrations.csv", ["student_id", "course_code"], data["regs"])
    w("teaching.csv", ["teacher_id", "course_code", "section_id"], data["teaching"])
    w("rooms.csv", ["room_id", "building", "bench_cols", "rows", "seats_per_bench", "priority"], data["rooms"])
    (out / "config.json").write_text(json.dumps(data["config"], indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=["base", "realistic"], default="base")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = a.out or Path(__file__).resolve().parent.parent / "data" / ("dummy" if a.variant == "base" else "dummy_realistic")
    data = build(a.variant, a.seed)
    write(data, out)
    print(f"wrote {out}: {sum(len(v) for v in data['rosters'].values())} students, {len(data['papers'])} papers, "
          f"{len(data['codes'])} course codes, {len(data['teachers'])} teachers, {len(data['rooms'])} rooms, "
          f"{len(data['regs'])} registrations")


if __name__ == "__main__":
    main()

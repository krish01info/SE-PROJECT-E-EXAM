"""A tiny dataset written to a temp dir, small enough to solve in seconds.

Two cohorts (A: 2 sections × 10, B: 1 section × 10). Cohort A writes P1, P2
and one of two electives (E1/E2); cohort B writes P3 and the shared paper
SH — offered to A as code SH-A and to B as code SH-B (many-codes-one-paper).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def write_dataset(root: Path, *, config_extra=None, rooms=None, teachers=None, extra_files=None):
    (root / "students").mkdir(parents=True, exist_ok=True)

    def w(name, header, rows):
        with (root / name).open("w", newline="") as fh:
            cw = csv.writer(fh)
            cw.writerow(header)
            cw.writerows(rows)

    w("sections.csv", ["section_id", "cohort_id"], [("A-S1", "A"), ("A-S2", "A"), ("B-S1", "B")])
    rosters = {"A-S1": [f"A1{i:02d}" for i in range(10)], "A-S2": [f"A2{i:02d}" for i in range(10)],
               "B-S1": [f"B1{i:02d}" for i in range(10)]}
    for sec, ids in rosters.items():
        w(f"students/{sec}.csv", ["student_id"], [[i] for i in ids])
    w("papers.csv", ["paper_id", "title", "department"],
      [("P1", "Paper One", "CSE"), ("P2", "Paper Two", "MATH"), ("E1", "Elective 1", "CSE"),
       ("E2", "Elective 2", "PHY"), ("P3", "Paper Three", "MGMT"), ("SH", "Shared", "MATH")])
    w("course_codes.csv", ["course_code", "paper_id", "cohort_id"],
      [("C-P1", "P1", "A"), ("C-P2", "P2", "A"), ("C-E1", "E1", "A"), ("C-E2", "E2", "A"),
       ("C-P3", "P3", "B"), ("SH-A", "SH", "A"), ("SH-B", "SH", "B")])
    regs = []
    a_students = rosters["A-S1"] + rosters["A-S2"]
    for i, s in enumerate(a_students):
        regs += [(s, "C-P1"), (s, "C-P2"), (s, "C-E1" if i % 2 else "C-E2")]
        if i < 4:
            regs.append((s, "SH-A"))
    for s in rosters["B-S1"]:
        regs += [(s, "C-P3"), (s, "SH-B")]
    w("registrations.csv", ["student_id", "course_code"], regs)
    w("teachers.csv", ["teacher_id", "rank", "department"], teachers or
      [("T1", "professor", "CSE"), ("T2", "assistant", "MATH"), ("T3", "associate", "MGMT"),
       ("T4", "assistant", "PHY"), ("T5", "assistant", "CSE"), ("PHD1", "phd", "CSE"), ("PHD2", "phd", "MATH"),
       ("PHD3", "phd", "MGMT")])
    w("teaching.csv", ["teacher_id", "course_code", "section_id"],
      [("T1", "C-P1", "A-S1"), ("T5", "C-P1", "A-S2"), ("T2", "C-P2", "A-S1"), ("T2", "C-P2", "A-S2"),
       ("T3", "C-P3", "B-S1"), ("T4", "C-E2", "A-S1"), ("T2", "SH-B", "B-S1")])
    w("rooms.csv", ["room_id", "building", "bench_cols", "rows", "seats_per_bench", "priority"], rooms or
      [("R1", "NB", 2, 4, 2, 0), ("R2", "NB", 2, 4, 2, 1), ("R3", "NB", 3, 4, 1, 2)])
    cfg = {"name": "tiny", "calendar": {"start": "2026-03-02", "end": "2026-03-13"},
           "scheduling": {"min_day_gap": 2, "time_limit_s": 10},
           "duties": {"time_limit_s": 10}, "solver": {"workers": 1, "seed": 1}}
    for k, v in (config_extra or {}).items():
        cfg.setdefault(k, {}).update(v) if isinstance(v, dict) else cfg.__setitem__(k, v)
    (root / "config.json").write_text(json.dumps(cfg))
    for name, text in (extra_files or {}).items():
        (root / name).write_text(text)
    return root


@pytest.fixture
def tiny(tmp_path) -> Path:
    return write_dataset(tmp_path / "tiny")

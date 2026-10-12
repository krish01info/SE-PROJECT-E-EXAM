"""Tests for every module, mapped to the SRS feature codes C1–C10."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from conftest import write_dataset
from ems import plan as P
from ems.conflicts import build_conflicts
from ems.feasibility import presolve_check
from ems.geometry import build_layout
from ems.ingest import ValidationError, load_dataset
from ems.mapping import build_paper_map
from ems.model import Room
from ems.pipeline import run_pipeline, transition
from ems.verify import verify_plan


# ---------------------------------------------------------------- C1 validation
def test_valid_dataset_loads(tiny):
    ds = load_dataset(tiny)
    assert len(ds.students) == 30 and len(ds.rooms) == 3
    assert not [i for i in ds.issues if i.severity == "error"]


def _error_rules(path):
    with pytest.raises(ValidationError) as e:
        load_dataset(path)
    return {(i.file, i.rule) for i in e.value.issues if i.severity == "error"}, e.value


def test_validation_reports_file_row_and_rule(tiny):
    with (tiny / "registrations.csv").open("a") as fh:
        fh.write("NOPE01,C-P1\nA100,NO-CODE\n")
    with (tiny / "teachers.csv").open("a") as fh:
        fh.write("T9,dean,CSE\n")
    with (tiny / "students" / "B-S1.csv").open("a") as fh:
        fh.write("A100\n")  # already in A-S1
    with (tiny / "teaching.csv").open("a") as fh:
        fh.write("T1,C-P3,A-S1\n")  # P3 is offered to cohort B, not A
    rules, err = _error_rules(tiny)
    assert ("registrations.csv", "unknown-student") in rules
    assert ("registrations.csv", "unknown-course-code") in rules
    assert ("teachers.csv", "bad-rank") in rules
    assert ("students/B-S1.csv", "student-in-two-sections") in rules
    assert ("teaching.csv", "cohort-mismatch") in rules
    assert "row" in err.report()


def test_validation_missing_file_and_columns(tmp_path):
    root = write_dataset(tmp_path / "d")
    (root / "rooms.csv").unlink()
    (root / "papers.csv").write_text("id,title\nX,Y\n")
    rules, _ = _error_rules(root)
    assert ("rooms.csv", "missing-file") in rules
    assert ("papers.csv", "missing-columns") in rules


# ---------------------------------------------------------------- C2/C3 mapping & conflicts
def test_many_codes_map_to_one_paper(tiny):
    ds = load_dataset(tiny)
    pm = build_paper_map(ds)
    assert pm.shared_papers == {"SH": ["SH-A", "SH-B"]}
    assert pm.size("SH") == 14  # 4 from cohort A + 10 from cohort B


def test_conflict_graph_is_registration_based(tiny):
    pm = build_paper_map(load_dataset(tiny))
    cg = build_conflicts(load_dataset(tiny), pm)
    assert cg.conflicts("P1", "P2") and cg.conflicts("P1", "E1")
    assert not cg.conflicts("E1", "E2")  # same cohort, different electives: no shared student
    assert cg.conflicts("SH", "P3") and cg.conflicts("SH", "P1")  # cross-cohort via the shared paper
    assert not cg.conflicts("P1", "P3")


# ---------------------------------------------------------------- geometry / stripes
@pytest.mark.parametrize("bench_cols,rows,spb", [(3, 6, 1), (3, 7, 2), (2, 5, 2), (4, 3, 1)])
def test_sides_have_no_internal_adjacency(bench_cols, rows, spb):
    lay = build_layout(Room("X", "B", bench_cols, rows, spb, 0), True, True)
    for side in (lay.side_a, lay.side_b):
        s = set(side)
        assert all(not (lay.neighbours[x] & s) for x in side)
    assert len(lay.side_a) + len(lay.side_b) == bench_cols * rows * spb
    assert abs(len(lay.side_a) - len(lay.side_b)) <= 1


def test_stripes_match_plan_section_4_3():
    s_room = build_layout(Room("S", "B", 3, 6, 1, 0), True, True)  # 2-wide benches, seat 1
    m_room = build_layout(Room("M", "B", 3, 7, 2, 0), False, True)  # 3-wide benches, no front/back
    assert len(s_room.stripes) == 6 and {len(s) for s in s_room.stripes} == {3}  # interleaved half-depth
    assert len(m_room.stripes) == 6 and {len(s) for s in m_room.stripes} == {7}  # full-depth left/right


# ---------------------------------------------------------------- C7 feasibility
def test_presolve_flags_too_few_days(tmp_path):
    root = write_dataset(tmp_path / "d", config_extra={"calendar": {"start": "2026-03-02", "end": "2026-03-04"}})
    ds = load_dataset(root)
    pm = build_paper_map(ds)
    rep = presolve_check(ds, pm, build_conflicts(ds, pm), [build_layout(r, True, True) for r in ds.rooms])
    assert not rep.ok
    assert any(f.code == "student-day-bound" and f.severity == "blocking" for f in rep.findings)


def test_presolve_flags_paper_too_large(tmp_path):
    root = write_dataset(tmp_path / "d", rooms=[("R1", "NB", 1, 4, 2, 0)])  # 4 seats per side
    ds = load_dataset(root)
    pm = build_paper_map(ds)
    rep = presolve_check(ds, pm, build_conflicts(ds, pm), [build_layout(r, True, True) for r in ds.rooms])
    assert any(f.code == "paper-too-large" for f in rep.findings) and not rep.ok


# ---------------------------------------------------------------- end-to-end (C4–C6, C10)
@pytest.fixture
def solved(tiny, tmp_path):
    out = tmp_path / "out"
    res = run_pipeline(tiny, out, log=lambda *_: None)
    assert res.ok, res.messages
    return tiny, out


def test_full_pipeline_passes_every_hard_rule(solved):
    _, out = solved
    v = json.loads((out / "verification.json").read_text())
    assert v["all_passed"], [c for c in v["hard"] if not c["passed"]]
    assert {c["id"] for c in v["hard"]} >= {f"H{i}" for i in range(1, 12)}
    for f in ["schedule.csv", "seating.csv", "duties.csv", "student_timetables.csv", "teacher_rosters.csv",
              "slot_summary.csv", "fairness.csv", "reports/index.html", "reports/summary.html",
              "reports/teacher_rosters.html", "reports/student_timetables.html"]:
        assert (out / f).exists(), f
    assert P.ExamPlan.load(out).state == P.REPORTED


def test_shared_paper_sits_in_one_slot(solved):
    _, out = solved
    with (out / "seating.csv").open() as fh:
        slots = {(r["date"], r["session"]) for r in csv.DictReader(fh) if r["paper_id"] == "SH"}
    assert len(slots) == 1


def test_verifier_catches_adjacency_violation(solved):
    _, out = solved
    path = out / "seating.csv"
    rows = list(csv.DictReader(path.open()))
    # put a neighbour of some student on the same paper by copying their paper id
    r0 = rows[0]
    key = (r0["date"], r0["session"], r0["room_id"])
    col = int(r0["col"]) + 1 if int(r0["col"]) == 1 else int(r0["col"]) - 1  # same bench neighbour
    occupant = next((r for r in rows if (r["date"], r["session"], r["room_id"]) == key
                     and r["row"] == r0["row"] and int(r["col"]) == col), None)
    if occupant:
        occupant["paper_id"] = r0["paper_id"]
    else:  # move another student of the same paper into the empty neighbouring seat
        mover = next(r for r in rows if r is not r0 and r["paper_id"] == r0["paper_id"]
                     and (r["date"], r["session"]) == key[:2])
        mover.update(room_id=r0["room_id"], row=r0["row"], col=str(col))
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    v = verify_plan(out)
    failed = {c["id"] for c in v["hard"] if not c["passed"]}
    assert "H5" in failed and not v["all_passed"]


# ---------------------------------------------------------------- C9 overrides, C8 diagnosis
def test_paper_pin_is_honoured(tiny, tmp_path):
    pins = tmp_path / "pins.csv"
    pins.write_text("kind,paper_id,teacher_id,room_id,date,session\npaper_slot,P3,,,2026-03-12,Evening\n")
    out = tmp_path / "o"
    res = run_pipeline(tiny, out, pins_file=pins, log=lambda *_: None)
    assert res.ok
    sched = {r["paper_id"]: (r["date"], r["session"]) for r in csv.DictReader((out / "schedule.csv").open())}
    assert sched["P3"] == ("2026-03-12", "Evening")


def test_conflicting_pins_are_diagnosed(tiny, tmp_path):
    pins = tmp_path / "pins.csv"
    pins.write_text("kind,paper_id,teacher_id,room_id,date,session\n"
                    "paper_slot,P1,,,2026-03-03,Morning\npaper_slot,P2,,,2026-03-04,Morning\n")
    out = tmp_path / "o"
    res = run_pipeline(tiny, out, pins_file=pins, log=lambda *_: None)
    assert not res.ok and res.state == P.INF_CAPACITY  # caught already by the pre-solve check
    assert "pins-conflict" in (out / "feasibility_report.txt").read_text()


def test_schedule_infeasibility_names_the_rules(tmp_path):
    # 7 exam days is exactly enough for 4 papers at gap 2 (days 0,2,4,6). Pinning P1 to day 0 and P2 to
    # day 3 is legal pairwise, but leaves no valid days for both the elective and SH -> solver proves
    # infeasibility and the diagnosis must name the pins and the gap rule.
    root = write_dataset(tmp_path / "d", config_extra={"calendar": {"start": "2026-03-02", "end": "2026-03-10"}})
    pins = tmp_path / "pins.csv"
    pins.write_text("kind,paper_id,teacher_id,room_id,date,session\npaper_slot,P1,,,2026-03-02,Morning\n"
                    "paper_slot,P2,,,2026-03-05,Morning\n")
    out = tmp_path / "o"
    res = run_pipeline(root, out, pins_file=pins, log=lambda *_: None)
    assert res.state == P.INF_SCHEDULE
    text = (out / "diagnosis.txt").read_text()
    assert "pinned-override" in text and "gap-rule" in text


def test_teacher_pin_into_own_class_is_rejected(solved, tmp_path):
    data, out = solved
    codes = {r["course_code"]: r["paper_id"] for r in csv.DictReader((data / "course_codes.csv").open())}
    taught = {(codes[r["course_code"]], r["section_id"]): r["teacher_id"]
              for r in csv.DictReader((data / "teaching.csv").open())}
    # a seat whose section was taught that paper by a known teacher
    seat, t = next((r, taught[(r["paper_id"], r["section_id"])]) for r in csv.DictReader((out / "seating.csv").open())
                   if (r["paper_id"], r["section_id"]) in taught)
    pins = tmp_path / "p.csv"
    pins.write_text(f"kind,paper_id,teacher_id,room_id,date,session\nteacher_room,,{t},{seat['room_id']},"
                    f"{seat['date']},{seat['session']}\n")
    res = run_pipeline(data, out, pins_file=pins, log=lambda *_: None)
    assert res.state == P.INF_DUTIES
    assert "taught" in (out / "diagnosis.txt").read_text()


# ---------------------------------------------------------------- state machine
def test_state_machine_rejects_illegal_transitions():
    plan = P.ExamPlan()
    plan.fire("dataset validated and mapped")
    with pytest.raises(P.TransitionError):
        plan.fire("allocate seats [no adjacent same paper]")  # cannot seat before scheduling
    with pytest.raises(P.TransitionError):
        plan.fire("HoD approves / publish plan")


def test_approval_locks_the_plan(solved):
    data, out = solved
    assert transition(out, "HoD approves / publish plan") == P.APPROVED
    res = run_pipeline(data, out, log=lambda *_: None)
    assert not res.ok and "may not change" in res.messages[0]

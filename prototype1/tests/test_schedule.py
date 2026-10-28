"""Step 4 tests: the schedule keeps the rules of model spec section 8.

Run from prototype1/:

    python -m pytest tests
"""

import csv
import datetime
import shutil
import sys
from pathlib import Path

import pytest

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import loader  # noqa: E402
import main  # noqa: E402
import schedule  # noqa: E402


def plan(dataset):
    """Load a dataset and schedule it. Returns (data, placements)."""
    data = loader.load(PROTOTYPE / "data" / dataset)
    return data, schedule.make_schedule(data)


def paper_dates_per_student(data, placements):
    """{student_id: [date of each paper they write]}"""
    dates = {}
    for placement in placements:
        for student in placement.paper.students:
            dates.setdefault(student, []).append(placement.date)
    return dates


# ---------------------------------------------------------------- the rules

@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_every_course_code_is_in_exactly_one_paper_and_slot(dataset):
    data, placements = plan(dataset)
    codes = [code for p in placements for code in p.paper.course_codes]
    assert sorted(codes) == sorted(c["course_code"] for c in data["courses"])


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_gap_rule_for_every_student(dataset):
    data, placements = plan(dataset)
    gap = data["settings"]["min_gap_days"]
    for student, dates in paper_dates_per_student(data, placements).items():
        dates.sort()
        for first, second in zip(dates, dates[1:]):
            assert (second - first).days >= gap, (student, first, second)


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_only_exam_days_are_used(dataset):
    data, placements = plan(dataset)
    allowed = set(schedule.exam_days(data["settings"]))
    assert all(p.date in allowed for p in placements)


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_no_session_goes_over_the_seat_limit(dataset):
    data, placements = plan(dataset)
    limit = sum(schedule.one_paper_seats(room) for room in data["rooms"])
    load = {}
    for p in placements:
        key = (p.date, p.session)
        load[key] = load.get(key, 0) + len(p.paper.students)
    assert max(load.values()) <= limit


def test_same_input_gives_same_plan():
    _, first = plan("main")
    _, second = plan("main")
    as_rows = lambda ps: [(p.date, p.session, p.paper.paper_id) for p in ps]
    assert as_rows(first) == as_rows(second)


# ---------------------------------------------------------------- the pieces

def test_seat_limit_of_rooms():
    assert schedule.one_paper_seats({"rows": "6", "seat_columns": "3"}) == 12
    assert schedule.one_paper_seats({"rows": "7", "seat_columns": "6"}) == 21
    data = loader.load(PROTOTYPE / "data" / "main")
    assert sum(schedule.one_paper_seats(r) for r in data["rooms"]) == 594


def test_exam_days_skip_weekends_and_holidays():
    data = loader.load(PROTOTYPE / "data" / "main")
    days = schedule.exam_days(data["settings"])
    assert len(days) == 14
    assert datetime.date(2026, 11, 11) not in days      # holiday
    assert datetime.date(2026, 11, 7) not in days       # Saturday


def test_tiny_schedule_worked_out_by_hand():
    # Biggest first, earliest day, emptier session, morning on a tie.
    # Ties in size go by paper ID: BIO2001 (3) is placed before PHY2001 (3).
    _, placements = plan("tiny")
    got = {(p.paper.paper_id, p.date.day, p.session) for p in placements}
    assert got == {
        ("CSE2001", 2, "morning"),
        ("CSE2002", 4, "morning"), ("ECE2001", 4, "evening"),
        ("MTH2001", 6, "morning"), ("PHY2002", 6, "evening"),
        ("BIO2001", 6, "morning"), ("PHY2001", 6, "evening"),
    }


# ---------------------------------------------------------------- output

def test_main_writes_schedule_csv(tmp_path, capsys):
    code = main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    files = list(tmp_path.glob("*/schedule.csv"))
    assert len(files) == 1
    with open(files[0], newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["date", "session", "paper_id", "course_codes",
                       "students"]
    assert rows[1] == ["2026-11-02", "morning", "CSE2001",
                       "CSE2001;CSE2003", "16"]
    assert "Fullest session: 2026-11-02 morning, 16 of 45 seats" in out


# ---------------------------------------------------------------- no plan

@pytest.fixture
def tiny(tmp_path):
    folder = tmp_path / "tiny"
    shutil.copytree(PROTOTYPE / "data" / "tiny", folder)
    return folder


def replace_text(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"test setup: {old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_window_too_short_for_the_gap_rule(tiny, tmp_path, capsys):
    # Every tiny student has 3 papers. Mon-Wed gives only Mon and Wed
    # with a clear day between, so the third paper has nowhere to go.
    replace_text(tiny / "settings.yaml", "end_date: 2026-11-06",
                 "end_date: 2026-11-04")
    out_root = tmp_path / "out"
    code = main.main([str(tiny), "--output", str(out_root)])
    out = capsys.readouterr().out
    assert code == 2
    assert "No plan possible." in out
    assert "break the gap rule" in out
    assert not out_root.exists()          # no partial plan is written


def test_not_enough_seats(tiny, tmp_path, capsys):
    # Only one S room: 12 seats, but CSE2001 has 16 students.
    (tiny / "rooms.csv").write_text("room_id,type,rows,seat_columns\n"
                                    "S01,S,6,3\n")
    code = main.main([str(tiny), "--output", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 2
    assert "Paper: CSE2001 (16 students)" in out
    assert "limit 12 seats" in out


def test_not_enough_teachers(tiny, tmp_path, capsys):
    # 16 students need S01 + S02 (24 seats): 2 rooms x 2 = 4 teachers.
    (tiny / "teachers.csv").write_text("teacher_id,rank\nT001,PROF\n"
                                       "T002,PROF\nT003,ASSOC\n")
    (tiny / "teaching.csv").write_text(
        "teacher_id,course_code,section_id\n"
        "T001,MTH2001,BT2CSE_I\nT001,CSE2002,BT2CSE_I\n"
        "T001,CSE2001,BT2CSE_I\nT001,PHY2001,BT2CSE_I\n"
        "T002,ECE2001,BT2ECOM_I\nT002,CSE2003,BT2ECOM_I\n"
        "T002,PHY2002,BT2ECOM_I\nT002,BIO2001,BT2ECOM_I\n")
    code = main.main([str(tiny), "--output", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 2, out
    assert "Paper: CSE2001 (16 students)" in out
    assert "3 teachers" in out

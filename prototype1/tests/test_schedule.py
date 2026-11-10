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
import duties  # noqa: E402
import seat  # noqa: E402


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
    # Biggest first; a session waiting for another paper is filled first.
    # Ties in size go by paper ID. (Since 2026-11-10 a paper goes where it
    # adds the fewest rooms; on tiny that gives the same schedule as the
    # old earliest-day way, and no fallback note.)
    # CSE2001 (16): 2 Nov morning; each section gets its own room, so both
    #   its teachers have a room. Everyone writes it, so 3 and 5 Nov are out.
    # CSE2002 (8): T004 teaches all of it, so alone it can't work: it waits
    #   in 4 Nov morning. ECE2001 (8) fills that waiting session.
    # MTH2001 (5) waits in 6 Nov morning; PHY2002 (5) fills it.
    # BIO2001 (3) and PHY2001 (3) fit in 6 Nov morning, so they go there
    #   (an empty evening alone would only be waiting).
    _, placements = plan("tiny")
    got = {(p.paper.paper_id, p.date.day, p.session) for p in placements}
    assert got == {
        ("CSE2001", 2, "morning"),
        ("CSE2002", 4, "morning"), ("ECE2001", 4, "morning"),
        ("MTH2001", 6, "morning"), ("PHY2002", 6, "morning"),
        ("BIO2001", 6, "morning"), ("PHY2001", 6, "morning"),
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


def only_why_txt(out_root):
    """No plan writes one new folder holding only why.txt (step 7)."""
    folders = list(out_root.iterdir())
    return len(folders) == 1 and [f.name for f in folders[0].iterdir()] == [
        "why.txt"]


def replace_text(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"test setup: {old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_window_too_short_for_the_gap_rule(tiny, tmp_path, capsys):
    # Every tiny student has 3 papers. Mon-Wed gives only Mon and Wed
    # with a clear day between, so the third paper has nowhere to go.
    # Since step 7 a cheap check finds this before scheduling.
    replace_text(tiny / "settings.yaml", "end_date: 2026-11-06",
                 "end_date: 2026-11-04")
    out_root = tmp_path / "out"
    code = main.main([str(tiny), "--output", str(out_root)])
    out = capsys.readouterr().out
    assert code == 2
    assert "No plan possible." in out
    assert "Rule: gap" in out
    assert "at most 2 papers fit" in out
    assert only_why_txt(out_root)         # no partial plan is written


def test_not_enough_seats(tiny, tmp_path, capsys):
    # Only one S room: 12 seats, but CSE2001 has 16 students. Since step 7
    # a cheap check finds this before scheduling.
    (tiny / "rooms.csv").write_text("room_id,type,rows,seat_columns\n"
                                    "S01,S,6,3\n")
    code = main.main([str(tiny), "--output", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 2
    assert "Rule: seats" in out
    assert "Paper: CSE2001 (16 students)" in out
    assert "give 12 seats to one paper" in out


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
    assert "Rule: paper placement" in out
    assert "Paper: CSE2001 (16 students)" in out
    assert "teachers: 10 sessions" in out
    assert "more teachers than the 3 there are" in out


def test_a_session_must_really_be_seatable_not_just_counted():
    # 13 + 5 + 3 = 21 students, and two S rooms give 24 one-paper seats, so
    # counting alone says yes. But step 5 can't seat it: A fills S01, then
    # B, C and A's last student would need S02 with three papers. So the
    # session does not fit. (This is what went wrong on 9 Nov evening.)
    rooms = [{"room_id": "S01", "type": "S", "rows": "6", "seat_columns": "3"},
             {"room_id": "S02", "type": "S", "rows": "6", "seat_columns": "3"}]
    papers = [schedule.Paper(name, [name],
                             {f"{name}{n:02d}" for n in range(count)})
              for name, count in (("A", 13), ("B", 5), ("C", 3))]
    limits = {"seat_limit": 24, "per_room": 2, "teacher_count": 99,
              "teaching": {}, "rank_of": {}, "section_of": None}
    assert not schedule.session_fits(papers, rooms, limits)
    assert schedule.session_fits(papers[:2], rooms, limits)


# ------------------------------------------- choosing a session (2026-11-10)
#
# Krish: fewer rooms means fewer duties, so teachers can check papers and do
# other work. A paper goes into the session where it adds the fewest rooms.

M01 = {"room_id": "M01", "type": "M", "rows": "7", "seat_columns": "6"}
S01 = {"room_id": "S01", "type": "S", "rows": "6", "seat_columns": "3"}
S02 = {"room_id": "S02", "type": "S", "rows": "6", "seat_columns": "3"}
NO_TEACHERS = {"per_room": 2, "teacher_count": 99, "teaching": {},
               "rank_of": {}, "section_of": None}
DAY_1 = datetime.date(2026, 11, 2)
DAY_2 = datetime.date(2026, 11, 3)


def placed_by(way, sizes, rooms, sessions):
    """Place made-up papers (no shared students, so no clashes) on two exam
    days in one way. Returns {paper_id: (date, session)}."""
    papers = {name: schedule.Paper(name, [name],
                                   {f"{name}{n:02d}" for n in range(count)})
              for name, count in sizes}
    limits = dict(NO_TEACHERS, seat_limit=sum(
        schedule.one_paper_seats(room) for room in rooms))
    placements = schedule.place_papers(
        way, papers, limits, schedule.build_clashes(papers), [DAY_1, DAY_2],
        sessions, 2, rooms, {})
    return {p.paper.paper_id: (p.date, p.session) for p in placements}


def test_a_paper_goes_where_it_adds_the_fewest_rooms():
    # Rooms: one M (21 seats for one paper) and two S (12 each). Papers A,
    # B and C have 21 students each. A and B take 2 Nov morning and evening
    # (the M room each, 1 room). C on 2 Nov would need both S rooms (2 more
    # rooms); on 3 Nov it gets the M room (1 more room). So C goes to 3 Nov:
    # 3 rooms in all.
    sizes = [("A", 21), ("B", 21), ("C", 21)]
    for way in (schedule.FEWEST_ROOMS_FEWER_STUDENTS,
                schedule.FEWEST_ROOMS_EARLIER_DAY):
        assert placed_by(way, sizes, [M01, S01, S02],
                         ["morning", "evening"]) == {
            "A": (DAY_1, "morning"), "B": (DAY_1, "evening"),
            "C": (DAY_2, "morning")}


def test_the_old_way_still_takes_the_earliest_day():
    # Same papers, the old way (the last fallback): C takes the earliest
    # day it fits, 2 Nov morning, in the two S rooms: 4 rooms in all.
    sizes = [("A", 21), ("B", 21), ("C", 21)]
    assert placed_by(schedule.EARLIEST_DAY, sizes, [M01, S01, S02],
                     ["morning", "evening"]) == {
        "A": (DAY_1, "morning"), "B": (DAY_1, "evening"),
        "C": (DAY_1, "morning")}


def test_tie_in_rooms_fewer_students_or_earlier_day():
    # One session a day. A (21) is on 2 Nov. B (5) adds 1 room on either
    # day: a tie. Way a takes the session with fewer students (3 Nov, empty:
    # less crowd at the same time). Way b takes the earlier day (2 Nov).
    sizes = [("A", 21), ("B", 5)]
    rooms = [M01, S01]
    assert placed_by(schedule.FEWEST_ROOMS_FEWER_STUDENTS, sizes, rooms,
                     ["morning"])["B"] == (DAY_2, "morning")
    assert placed_by(schedule.FEWEST_ROOMS_EARLIER_DAY, sizes, rooms,
                     ["morning"])["B"] == (DAY_1, "morning")


def test_session_check_gives_the_problem_and_the_room_count():
    papers = [schedule.Paper(name, [name],
                             {f"{name}{n:02d}" for n in range(count)})
              for name, count in (("A", 13), ("B", 5), ("C", 3))]
    limits = dict(NO_TEACHERS, seat_limit=24)
    assert schedule.session_check([], [S01, S02], limits) == (None, 0)
    assert schedule.session_check(papers[:2], [S01, S02], limits) == (None, 2)
    assert schedule.session_check(papers, [S01, S02], limits) == ("seats", 0)


def test_the_first_way_works_on_tiny_and_the_basis_says_so():
    data = loader.load(PROTOTYPE / "data" / "tiny")
    report = {}
    schedule.make_schedule(data, report)
    assert report == {"way": schedule.FEWEST_ROOMS_FEWER_STUDENTS,
                      "failed": []}
    line = schedule.basis_line(report)
    assert line.startswith("Timetable basis: biggest papers first")
    assert "on a tie, the session with fewer students" in line
    assert "Tried first" not in line


def test_main_falls_back_to_the_next_way_and_says_so():
    # On main, "fewest rooms, then fewer students" can't place every paper
    # (the gap rule leaves ECE2003 no day), so the next way makes the plan
    # and one note says so. (Krish: we have to make the plan, and the tool
    # should tell us it fell back.)
    data = loader.load(PROTOTYPE / "data" / "main")
    report = {}
    placements = schedule.make_schedule(data, report)
    assert len(placements) == 56
    assert report == {"way": schedule.FEWEST_ROOMS_EARLIER_DAY,
                      "failed": [schedule.FEWEST_ROOMS_FEWER_STUDENTS]}
    line = schedule.basis_line(report)
    assert "on a tie, the earlier day" in line
    assert ("Tried first, but could not place every paper: "
            f'"{schedule.FEWEST_ROOMS_FEWER_STUDENTS}".') in line


def test_two_ways_fail_then_the_old_way_makes_the_plan(monkeypatch, tmp_path,
                                                       capsys):
    # Pretend both new ways can't place every paper: the old way is used,
    # the plan is the old plan, and main.py says so on the screen and in
    # basis.txt.
    real = schedule.place_papers

    def only_the_old_way(way, *args):
        if way != schedule.EARLIEST_DAY:
            raise schedule.NoPlan("No plan possible.")
        return real(way, *args)

    monkeypatch.setattr(schedule, "place_papers", only_the_old_way)
    code = main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "Timetable basis: biggest papers first; each paper goes on the " \
           "earliest day it fits" in out
    assert (f'Tried first, but could not place every paper: '
            f'"{schedule.FEWEST_ROOMS_FEWER_STUDENTS}" and '
            f'"{schedule.FEWEST_ROOMS_EARLIER_DAY}".') in out
    assert len(list(tmp_path.glob("*/schedule.csv"))) == 1
    basis = next(tmp_path.glob("*/basis.txt")).read_text(encoding="utf-8")
    assert "Tried first, but could not place every paper" in basis


def test_no_plan_only_when_the_last_way_fails_too(monkeypatch):
    def nothing_works(way, *args):
        raise schedule.NoPlan(f"No plan possible.\nway: {way}")

    monkeypatch.setattr(schedule, "place_papers", nothing_works)
    data = loader.load(PROTOTYPE / "data" / "tiny")
    report = {}
    with pytest.raises(schedule.NoPlan) as error:
        schedule.make_schedule(data, report)
    assert schedule.EARLIEST_DAY in str(error.value)   # the last way's reason
    assert report == {}


def test_main_writes_basis_txt_and_prints_the_same_two_lines(tmp_path, capsys):
    # Krish (2026-11-10): the tool states on what basis the timetable and
    # the seating plan were made, on the screen and in the plan folder.
    code = main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    files = list(tmp_path.glob("*/basis.txt"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("Timetable basis: ")
    assert lines[1] == ("Seating basis: one paper per room, with the mix of "
                        "room sizes that needs the fewest rooms; 6 rooms hold "
                        "one paper and 1 holds two (two papers' leftovers "
                        "joined, or mixed where the rooms ran out).")
    assert lines[2] == main.TERMS_LINE
    for line in lines:
        assert line in out


def test_every_plan_folder_gets_terms_md(tmp_path, capsys):
    # Krish (2026-11-10): a page that explains the words of the plan, and
    # the output says to read it if a word is not clear.
    code = main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)])
    assert code == 0, capsys.readouterr().out
    copy = next(tmp_path.glob("*/terms.md")).read_text(encoding="utf-8")
    assert copy == main.TERMS_FILE.read_text(encoding="utf-8")
    for word in ("Fewest rooms", "On a tie, the session with fewer students",
                 "On a tie, the earlier day", "Tried first, but could not "
                 "place every paper", "Leftover", "Two papers' leftovers "
                 "joined", "Mixed where the rooms ran out"):
        assert word in copy, word


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_every_teacher_has_a_room_for_each_paper_they_teach(dataset):
    # The duty rule step 4 asks (duties.py): in the final plan, no teacher
    # (PhD scholars exempt) is left without a room for their paper.
    data, placements = plan(dataset)
    section_of = duties.section_of_student(data)
    seating = seat.make_seating(placements, data["rooms"], section_of,
                                schedule.room_check_for(data))
    limits = schedule.session_limits(data, schedule.build_papers(data))
    for slot, plans in seating.items():
        papers = [p.paper for p in placements if (p.date, p.session) == slot]
        assert duties.teachers_without_room(
            papers, plans, limits["teaching"], limits["rank_of"],
            section_of) == [], slot


def test_a_slot_still_waiting_at_the_end_is_no_plan(tiny, tmp_path, capsys):
    # T005 now teaches CSE2001 to BOTH sections, so CSE2001 can't be alone
    # in its slot. But every student writes CSE2001, so no other paper can
    # ever join it: the slot is still waiting at the end.
    with open(tiny / "teaching.csv", "a", encoding="utf-8") as file:
        file.write("T005,CSE2003,BT2ECOM_I\n")
    out_root = tmp_path / "out"
    code = main.main([str(tiny), "--output", str(out_root)])
    out = capsys.readouterr().out
    assert code == 2
    assert "Rule: duty room" in out
    assert "Slot: 2026-11-02 morning" in out
    assert "T005 (CSE2001)" in out
    assert only_why_txt(out_root)

"""Step 5 tests: the seating keeps the rules of model spec section 9, with
the step 5 change: two papers per room, never three.

Run from prototype1/:

    python -m pytest tests
"""

import csv
import sys
from pathlib import Path

import pytest

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import loader  # noqa: E402
import main  # noqa: E402
import schedule  # noqa: E402
import seat  # noqa: E402

S_ROOM = {"room_id": "S01", "type": "S", "rows": "6", "seat_columns": "3"}
M_ROOM = {"room_id": "M01", "type": "M", "rows": "7", "seat_columns": "6"}


def paper(paper_id, count):
    """A made-up paper with students PAPER01, PAPER02, ..."""
    students = {f"{paper_id}{n:02d}" for n in range(1, count + 1)}
    return schedule.Paper(paper_id, [paper_id], students)


def picture(room_plan):
    """The grid as text, like the room CSV: 'A01' for a seat, '.' if empty."""
    return [" ".join(cell[1] if cell else "." for cell in row)
            for row in room_plan.grid]


def full_seating(dataset):
    data = loader.load(PROTOTYPE / "data" / dataset)
    placements = schedule.make_schedule(data)
    return data, placements, seat.make_seating(placements, data["rooms"])


# ------------------------------------------------- small cases, by hand

def test_two_papers_worked_out_by_hand():
    # A has 20 students, B has 10. Rooms: S01 (6 x 3), then M01 (7 x 6).
    # S01: A is bigger -> columns 1 and 3 (12 seats): A01..A12.
    #      B -> column 2 (6 seats): B01..B06.   Left: A 8, B 4.
    # M01: A is bigger -> columns 1, 3, 5: A13..A19 down column 1, A20 at
    #      the front of column 3. B -> columns 2, 4, 6: B07..B10 in column 2.
    plans = seat.seat_slot([paper("A", 20), paper("B", 10)], [S_ROOM, M_ROOM])

    assert [p.room_id for p in plans] == ["S01", "M01"]
    assert picture(plans[0]) == [
        "A01 B01 A07",
        "A02 B02 A08",
        "A03 B03 A09",
        "A04 B04 A10",
        "A05 B05 A11",
        "A06 B06 A12",
    ]
    assert picture(plans[1]) == [
        "A13 B07 A20 . . .",
        "A14 B08 . . . .",
        "A15 B09 . . . .",
        "A16 B10 . . . .",
        "A17 . . . . .",
        "A18 . . . . .",
        "A19 . . . . .",
    ]


def test_finished_paper_leaves_its_seats_empty_no_third_paper():
    # S01 gets A (12, the most) and C (5). C runs out after 5 seats of
    # column 2; its 6th seat stays empty, B does NOT come in.
    # S02 gets B alone: columns 1 and 3 only.
    plans = seat.seat_slot([paper("A", 12), paper("B", 3), paper("C", 5)],
                           [S_ROOM, dict(S_ROOM, room_id="S02")])

    assert plans[0].papers == ["A", "C"]
    assert picture(plans[0])[5] == "A06 . A12"
    assert plans[1].papers == ["B"]
    assert picture(plans[1]) == ["B01 . .", "B02 . .", "B03 . .",
                                 ". . .", ". . .", ". . ."]


def test_a_pair_stays_together_until_one_paper_is_finished():
    # S01: A (40) + B (10). B has 4 left, C has 9: C now has more left, but
    # B keeps its place next to A until it is finished.
    # S02: A + B again (B's last 4). S03 and S04: A + C.
    rooms = [dict(S_ROOM, room_id=f"S0{n}") for n in (1, 2, 3, 4)]
    plans = seat.seat_slot([paper("A", 40), paper("B", 10), paper("C", 9)],
                           rooms)
    assert [p.papers for p in plans] == [["A", "B"], ["A", "B"],
                                         ["A", "C"], ["A", "C"]]


def test_one_paper_alone_uses_every_other_column():
    plans = seat.seat_slot([paper("A", 21)], [M_ROOM])
    for row in plans[0].grid:
        assert row[1] is None and row[3] is None and row[5] is None
        assert all(row[c] for c in (0, 2, 4))


def test_tie_in_size_goes_by_paper_id():
    plans = seat.seat_slot([paper("Z", 6), paper("Y", 6)], [S_ROOM])
    assert plans[0].papers == ["Y", "Z"]      # Y gets the odd columns


def test_only_rooms_in_use_are_returned():
    plans = seat.seat_slot([paper("A", 3)], [S_ROOM, M_ROOM])
    assert [p.room_id for p in plans] == ["S01"]


def test_rooms_run_out_raises_no_plan():
    # One S room seats at most 18 with two papers. 20 + 10 cannot fit.
    with pytest.raises(schedule.NoPlan) as error:
        seat.seat_slot([paper("A", 20), paper("B", 10)], [S_ROOM])
    message = str(error.value)
    assert "Rule: seats" in message
    assert "12 of 30 students still have no seat" in message
    assert "A (8)" in message and "B (4)" in message


# ------------------------------------------------- the rules, full datasets

@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_every_student_gets_exactly_one_seat_per_paper(dataset):
    data, placements, seating = full_seating(dataset)
    for placement in placements:
        slot = (placement.date, placement.session)
        seated = [cell[1] for plan in seating[slot] for row in plan.grid
                  for cell in row if cell and cell[0] == placement.paper.paper_id]
        assert sorted(seated) == sorted(placement.paper.students)


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_column_rule_and_at_most_two_papers_per_room(dataset):
    data, placements, seating = full_seating(dataset)
    for slot, plans in seating.items():
        for plan in plans:
            columns = list(zip(*plan.grid))
            papers_in = [{cell[0] for cell in column if cell}
                         for column in columns]
            for papers in papers_in:
                assert len(papers) <= 1, (slot, plan.room_id)  # one per column
            for left, right in zip(papers_in, papers_in[1:]):
                assert not (left & right), (slot, plan.room_id)
            assert len(set().union(*papers_in)) <= 2, (slot, plan.room_id)


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_students_sit_in_roll_order(dataset):
    # Reading each paper's seats in fill order (room, column, row) gives
    # the sorted student IDs.
    data, placements, seating = full_seating(dataset)
    for slot, plans in seating.items():
        order = {}
        for plan in plans:
            for column in zip(*plan.grid):
                for cell in column:
                    if cell:
                        order.setdefault(cell[0], []).append(cell[1])
        for students in order.values():
            assert students == sorted(students), slot


@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_a_room_is_used_once_per_slot(dataset):
    data, placements, seating = full_seating(dataset)
    for plans in seating.values():
        ids = [plan.room_id for plan in plans]
        assert len(ids) == len(set(ids))


def test_same_input_gives_same_seating():
    first = full_seating("main")[2]
    second = full_seating("main")[2]
    assert first == second


# ------------------------------------------------- the room CSV files

def test_main_writes_one_csv_per_room_in_use(tmp_path, capsys):
    code = main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)])
    assert code == 0
    data, placements, seating = full_seating("tiny")
    files = sorted(tmp_path.glob("*/daywise_seating_plans/*/*/*.csv"))
    assert len(files) == sum(len(plans) for plans in seating.values())

    front_room = tmp_path.glob(
        "*/daywise_seating_plans/2026-11-02/morning/S01.csv")
    with open(next(front_room), newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 6 and all(len(row) == 3 for row in rows)
    assert rows[0][0] == "CSE2001:BT2CSE0001"     # no header row
    assert rows[0][1] == ""                        # empty seat is blank

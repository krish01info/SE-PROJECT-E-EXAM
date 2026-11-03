"""Step 5 tests: the seating keeps the rules of model spec section 9: one
paper per room, two papers in a room only when the rooms run out (redone
2026-11-03).

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

S02 = dict(S_ROOM, room_id="S02")
S03 = dict(S_ROOM, room_id="S03")


def test_one_paper_per_room_next_batch_in_next_room():
    # A has 20 students, B has 10. Rooms: S01, M01, S02. Enough rooms, so no
    # mixing. A (bigger) goes first:
    # S01: odd columns 1 and 3 (12 seats): A01..A12.
    # M01: odd columns 1, 3, 5: A13..A19 down column 1, A20 at the front of
    #      column 3.
    # S02: B alone: B01..B06 in column 1, B07..B10 in column 3.
    plans = seat.seat_slot([paper("A", 20), paper("B", 10)],
                           [S_ROOM, M_ROOM, S02])

    assert [p.papers for p in plans] == [["A"], ["A"], ["B"]]
    assert picture(plans[0]) == [
        "A01 . A07",
        "A02 . A08",
        "A03 . A09",
        "A04 . A10",
        "A05 . A11",
        "A06 . A12",
    ]
    assert picture(plans[1]) == [
        "A13 . A20 . . .",
        "A14 . . . . .",
        "A15 . . . . .",
        "A16 . . . . .",
        "A17 . . . . .",
        "A18 . . . . .",
        "A19 . . . . .",
    ]
    assert picture(plans[2]) == [
        "B01 . B07",
        "B02 . B08",
        "B03 . B09",
        "B04 . B10",
        "B05 . .",
        "B06 . .",
    ]


def test_leftovers_are_mixed_when_rooms_run_out():
    # A 13, B 13, three S rooms. Alone they need 4 rooms (12 + 1 each).
    # So: A fills S01 alone, B fills S02 alone, and the leftovers A13 and
    # B13 share S03: A in column 1, B in column 2.
    plans = seat.seat_slot([paper("A", 13), paper("B", 13)],
                           [S_ROOM, S02, S03])

    assert [p.papers for p in plans] == [["A"], ["B"], ["A", "B"]]
    assert picture(plans[2]) == ["A13 B13 .", ". . .", ". . .",
                                 ". . .", ". . .", ". . ."]


def test_mixing_only_where_needed():
    # A 13, B 5, C 3, three S rooms. Alone they need 4 rooms, so we mix.
    # A fills S01. Leftovers: B 5, C 3, A 1. Two rooms are free for three
    # leftovers, so ONE room gets two papers: S02 = B + C. A's last student
    # gets S03 alone.
    plans = seat.seat_slot([paper("A", 13), paper("B", 5), paper("C", 3)],
                           [S_ROOM, S02, S03])

    assert [p.papers for p in plans] == [["A"], ["B", "C"], ["A"]]


def test_a_room_never_holds_a_third_paper():
    # As above but only two rooms. S02 takes B + C; A's last student would
    # be a third paper, so there is no plan.
    with pytest.raises(schedule.NoPlan) as error:
        seat.seat_slot([paper("A", 13), paper("B", 5), paper("C", 3)],
                       [S_ROOM, S02])
    message = str(error.value)
    assert "Rule: seats" in message
    assert "1 of 21 students still have no seat: A (1)" in message


def test_one_paper_alone_uses_every_other_column():
    plans = seat.seat_slot([paper("A", 21)], [M_ROOM])
    for row in plans[0].grid:
        assert row[1] is None and row[3] is None and row[5] is None
        assert all(row[c] for c in (0, 2, 4))


def test_tie_in_size_goes_by_paper_id():
    # Y and Z (6 each) can't have a room each: one room, so they mix, and
    # Y comes first (odd columns).
    plans = seat.seat_slot([paper("Z", 6), paper("Y", 6)], [S_ROOM])
    assert plans[0].papers == ["Y", "Z"]


def test_only_rooms_in_use_are_returned():
    plans = seat.seat_slot([paper("A", 3)], [S_ROOM, M_ROOM])
    assert [p.room_id for p in plans] == ["S01"]


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
def test_mixed_rooms_only_when_one_paper_per_room_does_not_fit(dataset):
    data, placements, seating = full_seating(dataset)
    for slot, plans in seating.items():
        if any(len(plan.papers) == 2 for plan in plans):
            papers = [p.paper for p in placements
                      if (p.date, p.session) == slot]
            assert seat.seat_alone(papers, data["rooms"]) is None, slot


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


# ------------------------------------------------- sections in new rooms

def test_each_section_starts_a_new_room_when_it_costs_no_extra_room():
    # A has 8 students of section X (A01..A08) and 8 of section Y
    # (A09..A16). Straight on: S01 12 (X and Y mixed) + S02 4 = 2 rooms.
    # By section: S01 8 X, S02 8 Y = also 2 rooms, so by section.
    section_of = {f"A{n:02d}": ("X" if n <= 8 else "Y") for n in range(1, 17)}
    plans = seat.seat_slot([paper("A", 16)], [S_ROOM, S02], section_of)
    first = {cell[1] for row in plans[0].grid for cell in row if cell}
    second = {cell[1] for row in plans[1].grid for cell in row if cell}
    assert first == {f"A{n:02d}" for n in range(1, 9)}
    assert second == {f"A{n:02d}" for n in range(9, 17)}


def test_sections_stay_together_when_a_new_room_would_cost_a_room():
    # 13 of X and 11 of Y. Straight on: 24 = S01 + S02 (2 rooms).
    # By section: X needs 2 rooms, Y 1 = 3 rooms. So straight on.
    section_of = {f"A{n:02d}": ("X" if n <= 13 else "Y") for n in range(1, 25)}
    plans = seat.seat_slot([paper("A", 24)], [S_ROOM, S02, S03], section_of)
    assert [p.room_id for p in plans] == ["S01", "S02"]

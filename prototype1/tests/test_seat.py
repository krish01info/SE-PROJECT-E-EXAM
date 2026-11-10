"""Step 5 tests: the seating keeps the rules of model spec section 9: one
paper per room; two papers in a room only for two papers' leftovers
(2026-11-10) or when the rooms run out (redone 2026-11-03).

Run from prototype1/:

    python -m pytest tests
"""

import csv
import sys
from pathlib import Path

import pytest

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import duties  # noqa: E402
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
    # The same seating main.py makes: with sections and the teacher check.
    return data, placements, seat.make_seating(
        placements, data["rooms"], duties.section_of_student(data),
        schedule.room_check_for(data))


# ------------------------------------------------- small cases, by hand

S02 = dict(S_ROOM, room_id="S02")
S03 = dict(S_ROOM, room_id="S03")


def test_one_paper_per_room_best_room_sizes():
    # A has 21 students, B has 12. Rooms: S01, M01, S02. Enough rooms, so no
    # mixing. Fewest rooms first (2026-11-09): A fits in M01 alone (21
    # seats), B in S01 (12), so 2 rooms. (The old way, rooms.csv order, gave
    # A S01 + M01 and B S02: 3 rooms.) Rooms come back in rooms.csv order.
    # Both rooms are full, so there is no leftover to join (2026-11-10).
    # M01: odd columns 1, 3, 5: A01..A07 down column 1, then A08..A14,
    #      then A15..A21.
    # S01: B alone: B01..B06 in column 1, B07..B12 in column 3.
    plans = seat.seat_slot([paper("A", 21), paper("B", 12)],
                           [S_ROOM, M_ROOM, S02])

    assert [p.room_id for p in plans] == ["S01", "M01"]
    assert [p.papers for p in plans] == [["B"], ["A"]]
    assert picture(plans[0]) == [
        "B01 . B07",
        "B02 . B08",
        "B03 . B09",
        "B04 . B10",
        "B05 . B11",
        "B06 . B12",
    ]
    assert picture(plans[1]) == [
        "A01 . A08 . A15 .",
        "A02 . A09 . A16 .",
        "A03 . A10 . A17 .",
        "A04 . A11 . A18 .",
        "A05 . A12 . A19 .",
        "A06 . A13 . A20 .",
        "A07 . A14 . A21 .",
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
def test_a_shared_room_holds_only_the_last_students_of_two_papers(dataset):
    # Changed 2026-11-10 (was: mixed rooms only when one paper per room does
    # not fit). Where the rooms don't run out, a room with two papers is two
    # leftovers joined: each paper is in at most one shared room, and the
    # students there are the last ones of that paper in roll order.
    data, placements, seating = full_seating(dataset)
    for slot, plans in seating.items():
        papers = {p.paper.paper_id: p.paper for p in placements
                  if (p.date, p.session) == slot}
        if seat.seat_alone(list(papers.values()), data["rooms"]) is None:
            continue            # rooms ran out: the mixing rules apply
        shared_rooms = {}
        for plan in plans:
            if len(plan.papers) != 2:
                continue
            for paper_id in plan.papers:
                shared_rooms[paper_id] = shared_rooms.get(paper_id, 0) + 1
                here = seat.students_of(plan, paper_id)
                everyone = sorted(papers[paper_id].students)
                assert here == everyone[-len(here):], (slot, plan.room_id)
        assert all(count == 1 for count in shared_rooms.values()), slot


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


# ------------------------------------------------- best room combination
# (2026-11-09, Krish: try the combinations of room sizes before seating,
# fewest rooms first, then fewest empty seats)

M02 = dict(M_ROOM, room_id="M02")


def room_ids(plans):
    return [plan.room_id for plan in plans]


def seated(plan):
    return sum(1 for row in plan.grid for cell in row if cell)


def test_45_students_get_one_m_and_two_s_rooms_with_no_empty_seat():
    # M + M + S would be 54 seats (9 empty). M + S + S is exactly 45.
    # The chosen rooms are filled in rooms.csv order: S01, S02, then M01.
    plans = seat.seat_slot([paper("A", 45)], [S_ROOM, S02, S03, M_ROOM, M02])
    assert room_ids(plans) == ["S01", "S02", "M01"]
    assert [seated(plan) for plan in plans] == [12, 12, 21]


def test_a_few_leftover_students_do_not_get_a_big_room():
    # 24 students. The old way (rooms.csv order) gave M01 21 and M02 only 3.
    # Every way needs 2 rooms; 2 S rooms leave no empty seat, so they win.
    plans = seat.seat_slot([paper("A", 24)], [M_ROOM, M02, S_ROOM, S02])
    assert room_ids(plans) == ["S01", "S02"]


def test_fewest_rooms_come_before_fewest_empty_seats():
    # 36 students: 3 S rooms have no empty seat, but 2 M rooms are fewer
    # rooms (fewer teachers on duty), so 2 M rooms.
    plans = seat.seat_slot([paper("A", 36)], [S_ROOM, S02, S03, M_ROOM, M02])
    assert room_ids(plans) == ["M01", "M02"]


def test_papers_share_the_rooms_of_the_slot():
    # A 21 and B 21, but only one M room and two S rooms: one of them gets
    # M01, the other S01 + S02 (both ways are 3 rooms, 3 empty seats).
    plans = seat.seat_slot([paper("A", 21), paper("B", 21)],
                           [S_ROOM, S02, M_ROOM])
    assert room_ids(plans) == ["S01", "S02", "M01"]
    assert plans[0].papers == plans[1].papers != plans[2].papers


def test_roll_order_kept_across_the_chosen_rooms():
    # The chosen rooms are filled in rooms.csv order, so reading them in
    # that order (column by column) gives the students in roll order.
    plans = seat.seat_slot([paper("A", 45)], [S_ROOM, S02, S03, M_ROOM, M02])
    order = [cell[1] for plan in plans for column in zip(*plan.grid)
             for cell in column if cell]
    assert order == sorted(order) and len(order) == 45


def test_a_teacher_with_no_room_makes_the_paper_split_by_section():
    # A: 8 of section X, 8 of section Y. Fewest rooms: all 16 in M01. But
    # the papers_short check says a teacher of A then has no room (both
    # sections in the only room), so A is split: X in S01, Y in S02.
    section_of = {f"A{n:02d}": ("X" if n <= 8 else "Y") for n in range(1, 17)}
    assert room_ids(seat.seat_slot([paper("A", 16)], [S_ROOM, S02, M_ROOM],
                                   section_of)) == ["M01"]

    def papers_short(plans):
        both = any({section_of[cell[1]] for row in plan.grid
                    for cell in row if cell} == {"X", "Y"} for plan in plans)
        return {"A"} if both else set()

    plans = seat.seat_slot([paper("A", 16)], [S_ROOM, S02, M_ROOM],
                           section_of, papers_short)
    assert room_ids(plans) == ["S01", "S02"]
    assert {cell[1] for row in plans[0].grid for cell in row if cell} == \
        {f"A{n:02d}" for n in range(1, 9)}


def test_old_way_is_the_backup_when_the_teacher_check_still_fails():
    # A has one section, so splitting can't help. If the check still says a
    # teacher has no room, seat_slot() gives the old way (rooms.csv order),
    # as before 2026-11-09; schedule.py then reports the problem.
    plans = seat.seat_slot([paper("A", 16)], [S_ROOM, S02, M_ROOM],
                           None, lambda plans: {"A"})
    assert room_ids(plans) == ["S01", "S02"]


def test_room_options_never_have_a_spare_room():
    # Every option seats everyone, and no single room could be left out.
    for students in range(1, 80):
        for option in seat.room_options(students, [21, 12], [18, 18]):
            seats = option[0] * 21 + option[1] * 12
            assert seats >= students
            if option[0]:
                assert seats - 21 < students
            if option[1]:
                assert seats - 12 < students


def test_no_rooms_means_no_best_way():
    assert seat.seat_best([paper("A", 3)], []) is None


# ------------------------------------------------- joining the leftovers
#
# Added 2026-11-10 (Krish): one paper per room stays the normal case; only
# two papers' leftovers (part-empty last rooms) are joined in one room.

M02 = dict(M_ROOM, room_id="M02")
M03 = dict(M_ROOM, room_id="M03")
M04 = dict(M_ROOM, room_id="M04")


def test_two_leftovers_share_one_room():
    # A 34 = M01 full (21) + 13 left. B 29 = one full M room (21) + 8 left.
    # Alone that is 4 rooms. The leftovers 13 and 8 share ONE room, so 3
    # rooms. The shared room is M04 (after both papers' full rooms, so roll
    # order is kept): A, the bigger leftover, in columns 1, 3, 5 and B in
    # columns 2, 4, 6.
    plans = seat.seat_slot([paper("A", 34), paper("B", 29)],
                           [M_ROOM, M02, M03, M04])

    assert room_ids(plans) == ["M01", "M03", "M04"]
    assert [p.papers for p in plans] == [["A"], ["B"], ["A", "B"]]
    assert picture(plans[2]) == [
        "A22 B22 A29 B29 . .",
        "A23 B23 A30 . . .",
        "A24 B24 A31 . . .",
        "A25 B25 A32 . . .",
        "A26 B26 A33 . . .",
        "A27 B27 A34 . . .",
        "A28 B28 . . . .",
    ]


def test_the_pair_that_fills_the_room_best_is_joined_first():
    # Leftovers: A 20, C 19, B 5 (each paper is one part-empty M room).
    # A + C leave 3 seats empty, A + B 17, C + B 18: so A and C are joined.
    # B has no partner left and stays alone.
    plans = seat.seat_slot([paper("A", 20), paper("B", 5), paper("C", 19)],
                           [M_ROOM, M02, M03])

    assert [p.papers for p in plans] == [["A", "C"], ["B"]]


def test_in_an_s_room_the_bigger_leftover_takes_the_two_odd_columns():
    # S room: 12 seats in columns 1 and 3, 6 seats in column 2. A 10 and
    # B 6 fit together in S01 (16 of 18 seats).
    plans = seat.seat_slot([paper("A", 10), paper("B", 6)], [S_ROOM, S02])

    assert room_ids(plans) == ["S01"]
    assert picture(plans[0]) == [
        "A01 B01 A07",
        "A02 B02 A08",
        "A03 B03 A09",
        "A04 B04 A10",
        "A05 B05 .",
        "A06 B06 .",
    ]


def test_full_rooms_are_never_joined():
    # Both rooms are full with one paper: nothing is a leftover.
    plans = seat.seat_slot([paper("A", 21), paper("B", 21)], [M_ROOM, M02])
    assert [p.papers for p in plans] == [["A"], ["B"]]


def test_a_leftover_with_no_partner_stays_alone():
    # A fills M01. B's 5 students are the only leftover: no one to join.
    plans = seat.seat_slot([paper("A", 21), paper("B", 5)], [M_ROOM, M02])
    assert [p.papers for p in plans] == [["A"], ["B"]]


def test_one_paper_alone_in_a_slot_is_never_joined_with_itself():
    plans = seat.seat_slot([paper("A", 30)], [M_ROOM, M02])
    assert [p.papers for p in plans] == [["A"], ["A"]]


def test_a_joined_room_never_gets_a_third_paper():
    # Three leftovers of 5: two share a room, the third stays alone.
    plans = seat.seat_slot([paper("A", 5), paper("B", 5), paper("C", 5)],
                           [M_ROOM, M02, M03])
    assert sorted(len(p.papers) for p in plans) == [1, 2]


def test_no_join_when_a_teacher_would_have_no_room():
    # The teacher check says no to every room with two papers, so the
    # leftovers stay in their own rooms.
    def papers_short(plans):
        return {"A"} if any(len(p.papers) == 2 for p in plans) else set()

    plans = seat.seat_slot([paper("A", 34), paper("B", 29)],
                           [M_ROOM, M02, M03, M04], None, papers_short)
    assert [p.papers for p in plans] == [["A"], ["A"], ["B"], ["B"]]


def test_no_join_that_would_break_roll_order():
    # A 5 sits in S01, B 26 in S02 (12) + M01... the only room both
    # leftovers fit in must come after the other paper's rooms. Whatever is
    # joined, each paper still reads in roll order across the rooms.
    plans = seat.seat_slot([paper("A", 5), paper("B", 26)],
                           [S_ROOM, S02, M_ROOM, M02])
    for paper_id in ("A", "B"):
        order = [cell[1] for plan in plans for column in zip(*plan.grid)
                 for cell in column if cell and cell[0] == paper_id]
        assert order == sorted(order)
    assert sum(1 for plan in plans for row in plan.grid
               for cell in row if cell) == 31


def test_join_leftovers_with_no_rooms_or_plans():
    assert seat.join_leftovers([], []) == []


def test_basis_line_when_every_room_holds_one_paper():
    plans = seat.seat_slot([paper("A", 21), paper("B", 21)], [M_ROOM, M02])
    assert seat.basis_line({("day", "morning"): plans}) == (
        "Seating basis: one paper per room, with the mix of room sizes that "
        "needs the fewest rooms; all 2 rooms hold one paper.")

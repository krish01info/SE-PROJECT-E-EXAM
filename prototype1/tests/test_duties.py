"""Tests for the duty rule step 4 asks (duties.py, model spec section 10).

Run from prototype1/:

    python -m pytest tests
"""

import sys
from pathlib import Path

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import duties  # noqa: E402
import seat  # noqa: E402

SECTION_OF = {"a1": "A_I", "a2": "A_II", "b1": "B_I"}


def room(room_id, *cells):
    """A one-row RoomPlan holding the given (paper_id, student_id) cells."""
    papers = sorted({cell[0] for cell in cells})
    return seat.RoomPlan(room_id, papers, [list(cells)])


# Paper P is written by sections A_I (a1) and A_II (a2); paper Q by B_I (b1).
R1 = room("R1", ("P", "a1"))
R2 = room("R2", ("P", "a2"))
R3 = room("R3", ("Q", "b1"))


def test_first_choice_is_a_room_with_the_paper_but_none_of_own_students():
    # Teaches P to A_I only: R2 has P and no A_I student.
    teaches = {("P", "A_I")}
    assert duties.paper_duty_rooms("P", teaches, [R1, R2, R3],
                                   SECTION_OF) == ["R2"]


def test_otherwise_a_room_with_a_different_paper():
    # Teaches P to both sections: every P room has own students, so the
    # teacher gets a room with a different paper (R3) in the same slot.
    teaches = {("P", "A_I"), ("P", "A_II")}
    assert duties.paper_duty_rooms("P", teaches, [R1, R2, R3],
                                   SECTION_OF) == ["R3"]


def test_never_a_room_with_own_students_of_any_paper():
    # Teaches P to both sections and Q to B_I: no room is allowed.
    teaches = {("P", "A_I"), ("P", "A_II"), ("Q", "B_I")}
    assert duties.paper_duty_rooms("P", teaches, [R1, R2, R3],
                                   SECTION_OF) == []


def test_teachers_without_room_lists_them_and_skips_phd_scholars():
    class Paper:
        def __init__(self, paper_id):
            self.paper_id = paper_id

    teaching = {"T1": {("P", "A_I"), ("P", "A_II")},     # alone: no room
                "T2": {("P", "A_I"), ("P", "A_II")}}     # PhD: exempt
    rank_of = {"T1": "ASST", "T2": "PHD"}
    missing = duties.teachers_without_room([Paper("P")], [R1, R2], teaching,
                                           rank_of, SECTION_OF)
    assert missing == [("T1", "P")]

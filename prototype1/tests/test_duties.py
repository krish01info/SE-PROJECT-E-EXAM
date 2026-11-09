"""Tests for duties.py (model spec section 10): the rule step 4 asks, and
step 6, make_duties().

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


# ================================================== step 6: make_duties()

import csv  # noqa: E402
import datetime  # noqa: E402

import pytest  # noqa: E402

import loader  # noqa: E402
import main  # noqa: E402
import schedule  # noqa: E402
from errors import NoPlan  # noqa: E402

DAY_1 = datetime.date(2026, 11, 2)
DAY_2 = datetime.date(2026, 11, 3)


def hand_data(teachers, teaching_rows, per_room):
    """A made-up input: `teachers` is {teacher_id: rank}, `teaching_rows`
    (teacher, paper, section) with one course code per paper."""
    return {
        "settings": {"invigilators_per_room": per_room,
                     "sessions": ["morning", "evening"]},
        "teachers": [{"teacher_id": t, "rank": r} for t, r in teachers.items()],
        "teaching": [{"teacher_id": t, "course_code": p, "section_id": s}
                     for t, p, s in teaching_rows],
        "students": [{"student_id": student, "section_id": section}
                     for student, section in SECTION_OF.items()],
    }


HAND_PAPERS = {"P": schedule.Paper("P", ["P"]), "Q": schedule.Paper("Q", ["Q"])}


def rooms_of(rows):
    """{room_id: sorted teacher IDs} for duty rows of one slot."""
    found = {}
    for _day, _session, room_id, teacher_id in rows:
        found.setdefault(room_id, []).append(teacher_id)
    return found


def test_own_paper_duty_comes_first():
    # T1 teaches P to A_I: the only room that counts as their P duty is R2
    # (P, no A_I student). Without the own-paper rule T1, the lowest ID,
    # would take R1. One teacher per room.
    data = hand_data({"T1": "ASST", "T2": "ASST", "T3": "ASST"},
                     [("T1", "P", "A_I")], per_room=1)
    rows = duties.make_duties({(DAY_1, "morning"): [R1, R2, R3]}, data,
                              HAND_PAPERS)
    assert rooms_of(rows) == {"R1": ["T2"], "R2": ["T1"], "R3": ["T3"]}


def test_chain_of_moves_finds_a_place():
    # One teacher per room. T1 may sit in R1 or R2, T2 in R2 or R3, T3 in R1
    # or R2. T1 takes R1, T2 takes R2; for T3 both are full. Chain: T3 takes
    # R1, T1 moves to R2, T2 moves to R3. Without the chain T3 would have no
    # room.
    may = {"T1": {"R1", "R2"}, "T2": {"R2", "R3"}, "T3": {"R1", "R2"}}
    state = duties.SlotDuties([R1, R2, R3], per_room=1)

    def may_sit(teacher_id, room_id):
        return room_id in may[teacher_id]

    for teacher_id in ["T1", "T2", "T3"]:
        assert duties.place_teacher(teacher_id, state, may_sit, set())
    assert state.room_of == {"T1": "R2", "T2": "R3", "T3": "R1"}


def test_chain_that_fails_changes_nothing():
    may = {"T1": {"R1"}, "T2": {"R1"}}
    state = duties.SlotDuties([R1], per_room=1)

    def may_sit(teacher_id, room_id):
        return room_id in may[teacher_id]

    assert duties.place_teacher("T1", state, may_sit, set())
    assert not duties.place_teacher("T2", state, may_sit, set())
    assert state.room_of == {"T1": "R1"}


def test_phd_scholars_only_when_no_regular_teacher_is_free():
    data = hand_data({"T1": "PROF", "T2": "ASST", "T9": "PHD"}, [], per_room=2)
    rows = duties.make_duties({(DAY_1, "morning"): [R3]}, data, HAND_PAPERS)
    assert rooms_of(rows) == {"R3": ["T1", "T2"]}

    data = hand_data({"T1": "PROF", "T9": "PHD"}, [], per_room=2)
    rows = duties.make_duties({(DAY_1, "morning"): [R3]}, data, HAND_PAPERS)
    assert rooms_of(rows) == {"R3": ["T1", "T9"]}


def test_second_shift_on_a_day_comes_after_fewest_duties():
    # Krish's order (i): T1 has fewer duties but already works on DAY_1, so
    # T2 is picked first on DAY_1. On DAY_2 the counts decide.
    counts = {"T1": 1, "T2": 3}
    days_worked = {"T1": {DAY_1}, "T2": set()}
    assert duties.best_first(["T1", "T2"], DAY_1, counts,
                             days_worked) == ["T2", "T1"]
    assert duties.best_first(["T1", "T2"], DAY_2, counts,
                             days_worked) == ["T1", "T2"]


def test_evening_goes_to_someone_free_that_day():
    data = hand_data({"T1": "ASST", "T2": "ASST"}, [], per_room=1)
    rows = duties.make_duties({(DAY_1, "morning"): [R3],
                               (DAY_1, "evening"): [R3]}, data, HAND_PAPERS)
    assert [(row[1], row[3]) for row in rows] == [("morning", "T1"),
                                                  ("evening", "T2")]


def test_no_plan_when_teachers_run_out():
    data = hand_data({"T1": "ASST"}, [], per_room=2)
    with pytest.raises(NoPlan) as error:
        duties.make_duties({(DAY_1, "morning"): [R3]}, data, HAND_PAPERS)
    assert "Rule: duties" in str(error.value)
    assert "R3 has 1" in str(error.value)


def test_no_plan_when_own_paper_rooms_are_full():
    # T1 and T2 both teach P to A_I and A_II: their only room is R3 (a
    # different paper), and it has one place.
    data = hand_data({"T1": "ASST", "T2": "ASST"},
                     [("T1", "P", "A_I"), ("T1", "P", "A_II"),
                      ("T2", "P", "A_I"), ("T2", "P", "A_II")], per_room=1)
    with pytest.raises(NoPlan) as error:
        duties.make_duties({(DAY_1, "morning"): [R1, R2, R3]}, data,
                           HAND_PAPERS)
    assert "Rule: duty room" in str(error.value)


def test_no_plan_when_two_own_papers_need_different_rooms():
    # T1 teaches P to A_I and Q to B_I, both written in this slot. Their P
    # duty counts only in R2 (P, no A_I), their Q duty only in R4 (Q, no
    # B_I). One duty per slot can't be both.
    r4 = room("R4", ("Q", "b2"))
    data = hand_data({"T1": "ASST"}, [("T1", "P", "A_I"), ("T1", "Q", "B_I")],
                     per_room=1)
    data["students"].append({"student_id": "b2", "section_id": "B_II"})
    with pytest.raises(NoPlan) as error:
        duties.make_duties({(DAY_1, "morning"): [R1, R2, R3, r4]}, data,
                           HAND_PAPERS)
    assert "no one room counts" in str(error.value)


# ------------------------------------------------- the real datasets

@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_every_rule_holds_on_real_data(dataset):
    data = loader.load(PROTOTYPE / "data" / dataset)
    section_of = duties.section_of_student(data)
    placements = schedule.make_schedule(data)
    seating = seat.make_seating(placements, data["rooms"], section_of,
                                schedule.room_check_for(data))
    papers = schedule.build_papers(data)
    rows = duties.make_duties(seating, data, papers)
    teaching = duties.build_teaching(data, papers)
    rank_of = {t["teacher_id"]: t["rank"] for t in data["teachers"]}
    per_room = data["settings"]["invigilators_per_room"]

    for (day, session), plans in seating.items():
        slot_rows = [row for row in rows if row[:2] == (day, session)]
        in_room = rooms_of(slot_rows)
        teachers = [row[3] for row in slot_rows]
        assert len(teachers) == len(set(teachers))          # one per slot
        assert set(in_room) == {plan.room_id for plan in plans}
        for plan in plans:
            assert len(in_room[plan.room_id]) == per_room
            inside = duties.room_contents(plan, section_of)
            for teacher_id in in_room[plan.room_id]:
                assert not inside & teaching.get(teacher_id, set())
        # every regular teacher's own paper in this slot: a room that counts
        papers_here = {p for plan in plans for p in plan.papers}
        for teacher_id, teaches in teaching.items():
            if rank_of[teacher_id] == duties.PHD:
                continue
            mine = [row[2] for row in slot_rows if row[3] == teacher_id]
            for paper_id in {pair[0] for pair in teaches} & papers_here:
                assert mine and mine[0] in duties.paper_duty_rooms(
                    paper_id, teaches, plans, section_of)

    if dataset == "main":
        numbers = duties.duty_summary(rows, data)
        assert numbers["phd_duties"] == 0
        assert numbers["most"] - numbers["fewest"] <= 1


def test_main_writes_duties_csv(tmp_path):
    assert main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)]) == 0
    folder = next(tmp_path.iterdir())
    with open(folder / "duties.csv", newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["date", "session", "room_id", "teacher_id"]
    room_files = list((folder / "daywise_seating_plans").glob("*/*/*.csv"))
    assert len(rows) - 1 == 2 * len(room_files)

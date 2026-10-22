import unittest

from resources import ResourceError, SlotPlanner


def planner_for(sizes, room_count=2, teacher_count=4, teaching=None, sections=None, ranks=None):
    registrations = [
        {"student_id": student, "course_code": code}
        for code, students in sizes.items() for student in students
    ]
    papers = [
        {"paper_id": code, "course_codes": [code], "students": sorted(students)}
        for code, students in sizes.items()
    ]
    return SlotPlanner(
        papers,
        [{"room_id": f"S{i}", "rows": 6, "seat_columns": 3} for i in range(room_count)],
        [{"teacher_id": f"T{i}", "rank": (ranks or {}).get(f"T{i}", "ASST")} for i in range(teacher_count)],
        teaching or [], registrations,
        sections or {row["student_id"]: "SEC" for row in registrations}, 2,
    ), papers


def students_in(room):
    return [cell[1] for column in zip(*room.seats) for cell in column if cell]


class ResourceTests(unittest.TestCase):
    def test_single_paper_capacity_uses_alternate_columns(self):
        planner, papers = planner_for({"A": [f"A{i:02}" for i in range(13)]}, room_count=1)
        with self.assertRaisesRegex(ResourceError, "column rule allows at most 12"):
            planner.plan(papers)

    def test_prefers_separate_rooms_and_preserves_roll_and_room_order(self):
        planner, papers = planner_for({"A": ["A2", "A1"], "B": ["B2", "B1"]})
        plan = planner.plan(papers)
        self.assertEqual([r.room_id for r in plan.rooms], ["S0", "S1"])
        self.assertEqual(students_in(plan.rooms[0]), ["A1", "A2"])
        self.assertEqual(students_in(plan.rooms[1]), ["B1", "B2"])

    def test_mixes_only_when_separate_rooms_run_out(self):
        planner, papers = planner_for(
            {"A": [f"A{i:02}" for i in range(12)], "B": [f"B{i:02}" for i in range(6)]},
            room_count=1, teacher_count=2,
        )
        room = planner.plan(papers).rooms[0]
        self.assertEqual([next(cell[0] for cell in col if cell) for col in zip(*room.seats)], ["A", "B", "A"])
        self.assertEqual(len(students_in(room)), 18)

    def test_retries_an_unstaffable_seating_arrangement(self):
        sizes = {"A": ["A01"] + [f"B{i:02}" for i in range(12)]}
        sections = {student: student[0] for student in sizes["A"]}
        teaching = [
            {"teacher_id": "T0", "course_code": "A", "section_id": "A"},
            {"teacher_id": "T1", "course_code": "A", "section_id": "B"},
        ]
        planner, papers = planner_for(sizes, teaching=teaching, sections=sections)
        plan = planner.plan(papers)
        # The fullest first room mixes sections and leaves T1 no eligible room.
        # Retrying with one A student, then twelve B students, allows both duties.
        self.assertEqual(students_in(plan.rooms[0]), ["A01"])
        self.assertEqual(students_in(plan.rooms[1]), sorted(sizes["A"])[1:])
        self.assertIn("T1", plan.rooms[0].teachers)
        self.assertIn("T0", plan.rooms[1].teachers)
        self.assertEqual(plan.exemptions, [])

    def test_exemption_does_not_allow_supervising_own_students(self):
        teaching = [{"teacher_id": "T0", "course_code": "A", "section_id": "SEC"}]
        planner, papers = planner_for({"A": ["A1"]}, teaching=teaching, teacher_count=3)
        plan = planner.plan(papers)
        self.assertEqual(plan.exemptions, [("T0", "A")])
        self.assertNotIn("T0", plan.rooms[0].teachers)

    def test_exemption_does_not_create_an_extra_eligible_invigilator(self):
        teaching = [{"teacher_id": "T0", "course_code": "A", "section_id": "SEC"}]
        planner, papers = planner_for({"A": ["A1"]}, teaching=teaching, teacher_count=2)
        with self.assertRaisesRegex(ResourceError, "invigilators"):
            planner.plan(papers)

    def test_phd_has_no_own_paper_requirement_but_still_cannot_supervise_own_class(self):
        teaching = [{"teacher_id": "T0", "course_code": "A", "section_id": "X"}]
        planner, papers = planner_for(
            {"A": ["A1", "A2"]}, teaching=teaching, teacher_count=3,
            sections={"A1": "X", "A2": "Y"}, ranks={"T0": "PHD"},
        )
        plan = planner.plan(papers)
        self.assertEqual(len(plan.rooms), 1)
        self.assertNotIn("T0", plan.rooms[0].teachers)

    def test_catches_shared_eligible_teacher_shortage_across_rooms(self):
        teaching = [
            {"teacher_id": f"T{i}", "course_code": "A", "section_id": "SEC"}
            for i in range(4)
        ]
        planner, papers = planner_for(
            {"A": [f"A{i:02}" for i in range(13)]}, teaching=teaching, teacher_count=6,
        )
        # Each room has two eligible teachers, but both rooms need the same two.
        with self.assertRaisesRegex(ResourceError, "invigilators"):
            planner.plan(papers)

    def test_shared_codes_do_not_falsely_exempt_a_teacher_of_only_one_cohort(self):
        papers = [{"paper_id": "A", "course_codes": ["A", "B"], "students": ["A1", "B1"]}]
        planner = SlotPlanner(
            papers, [{"room_id": f"S{i}", "rows": 6, "seat_columns": 3} for i in range(2)],
            [{"teacher_id": f"T{i}", "rank": "ASST"} for i in range(4)],
            [{"teacher_id": "T0", "course_code": "A", "section_id": "X"}],
            [{"student_id": "A1", "course_code": "A"}, {"student_id": "B1", "course_code": "B"}],
            {"A1": "X", "B1": "Y"}, 2,
        )
        plan = planner.plan(papers)
        self.assertEqual(plan.exemptions, [])
        self.assertEqual(len(plan.rooms), 2)
        other_class = next(room for room in plan.rooms if students_in(room) == ["B1"])
        self.assertIn("T0", other_class.teachers)

    def test_shared_code_exemption_requires_teaching_all_cohorts(self):
        papers = [{"paper_id": "A", "course_codes": ["A", "B"], "students": ["A1", "B1"]}]
        planner = SlotPlanner(
            papers, [{"room_id": "S0", "rows": 6, "seat_columns": 3}],
            [{"teacher_id": f"T{i}", "rank": "ASST"} for i in range(3)],
            [
                {"teacher_id": "T0", "course_code": "A", "section_id": "X"},
                {"teacher_id": "T0", "course_code": "B", "section_id": "Y"},
            ],
            [{"student_id": "A1", "course_code": "A"}, {"student_id": "B1", "course_code": "B"}],
            {"A1": "X", "B1": "Y"}, 2,
        )
        plan = planner.plan(papers)
        self.assertEqual(plan.exemptions, [("T0", "A")])
        self.assertNotIn("T0", plan.rooms[0].teachers)


if __name__ == "__main__":
    unittest.main()

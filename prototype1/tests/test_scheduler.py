import unittest
from datetime import date

from scheduler import NoScheduleError, schedule_papers


def settings(start, end, weekdays, min_gap_days=2):
    return {
        "start_date": date.fromisoformat(start),
        "end_date": date.fromisoformat(end),
        "exam_weekdays": weekdays,
        "holidays": [],
        "sessions": ["morning", "evening"],
        "min_gap_days": min_gap_days,
        "invigilators_per_room": 2,
    }


def resources(registrations):
    return {
        "rooms": [{"room_id": f"M{i}", "rows": 7, "seat_columns": 6} for i in range(3)],
        "teachers": [{"teacher_id": f"T{i}", "rank": "PHD"} for i in range(6)],
        "teaching": [],
        "student_sections": {row["student_id"]: "SEC" for row in registrations},
    }


class SchedulePapersTests(unittest.TestCase):
    def test_groups_shared_paper_and_respects_student_exam_gap(self):
        courses = [
            {"course_code": "A1", "cohort_id": "C1"},
            {"course_code": "A2", "cohort_id": "C2"},
            {"course_code": "B1", "cohort_id": "C1"},
            {"course_code": "C1", "cohort_id": "C3"},
        ]
        registrations = [
            {"student_id": "S1", "course_code": "A1"},
            {"student_id": "S2", "course_code": "A2"},
            {"student_id": "S1", "course_code": "B1"},
            {"student_id": "S3", "course_code": "C1"},
        ]
        plan = schedule_papers(
            courses,
            registrations,
            settings("2026-11-02", "2026-11-06", ["Mon", "Tue", "Wed", "Thu", "Fri"]),
            {"same_paper": [["A1", "A2"]]},
            **resources(registrations),
        ).schedule

        self.assertEqual({row["paper_id"] for row in plan}, {"A1", "B1", "C1"})
        shared = next(row for row in plan if row["paper_id"] == "A1")
        self.assertEqual(shared["course_codes"], ["A1", "A2"])
        self.assertEqual(shared["students"], ["S1", "S2"])
        exams_for_s1 = sorted(row["date"] for row in plan if "S1" in row["students"])
        self.assertGreaterEqual((exams_for_s1[1] - exams_for_s1[0]).days, 2)
        self.assertTrue(all(row["session"] in ["morning", "evening"] for row in plan))

    def test_backtracks_to_find_a_plan_after_first_choices_dead_end(self):
        courses = [{"course_code": code, "cohort_id": "C"} for code in ["P1", "P4", "P2", "P3"]]
        registrations = [
            {"student_id": "S12", "course_code": "P1"},
            {"student_id": "S12", "course_code": "P2"},
            {"student_id": "S23", "course_code": "P2"},
            {"student_id": "S23", "course_code": "P3"},
            {"student_id": "S34", "course_code": "P3"},
            {"student_id": "S34", "course_code": "P4"},
        ]
        plan = schedule_papers(
            courses,
            registrations,
            settings("2026-11-02", "2026-11-04", ["Mon", "Wed"]),
            {"same_paper": []},
            **resources(registrations),
        ).schedule

        self.assertEqual(len(plan), 4)
        self.assertEqual({row["date"] for row in plan}, {date(2026, 11, 2), date(2026, 11, 4)})
        for student in ["S12", "S23", "S34"]:
            dates = [row["date"] for row in plan if student in row["students"]]
            self.assertEqual(len(dates), 2)
            self.assertGreaterEqual(abs((dates[1] - dates[0]).days), 2)

    def test_raises_when_exam_window_cannot_fit_student_gap(self):
        courses = [
            {"course_code": "A", "cohort_id": "C"},
            {"course_code": "B", "cohort_id": "C"},
        ]
        registrations = [
            {"student_id": "S1", "course_code": "A"},
            {"student_id": "S1", "course_code": "B"},
        ]
        with self.assertRaises(NoScheduleError):
            schedule_papers(
                courses,
                registrations,
                settings("2026-11-02", "2026-11-03", ["Mon", "Tue"]),
                {"same_paper": []},
                **resources(registrations),
            )

    def test_moves_a_paper_to_the_other_session_when_seats_run_out(self):
        registrations = [
            {"student_id": f"{code}{i:02}", "course_code": code}
            for code in ["A", "B"] for i in range(12)
        ]
        inputs = resources(registrations)
        inputs["rooms"] = [{"room_id": "S1", "rows": 6, "seat_columns": 3}]
        plan = schedule_papers(
            [{"course_code": code} for code in ["A", "B"]], registrations,
            settings("2026-11-02", "2026-11-02", ["Mon"]), {}, **inputs,
        )
        self.assertEqual(len(plan.slots), 2)
        self.assertEqual({row["session"] for row in plan.schedule}, {"morning", "evening"})

    def test_backtracks_after_exact_teacher_check_fails(self):
        registrations = [
            {"student_id": f"{code}{section}", "course_code": code}
            for code in ["A", "B"] for section in ["X", "Y"]
        ]
        inputs = resources(registrations)
        inputs["rooms"] = [
            {"room_id": f"S{i}", "rows": 6, "seat_columns": 3} for i in range(2)
        ]
        inputs["teachers"] = [{"teacher_id": f"T{i}", "rank": "ASST"} for i in range(4)]
        inputs["student_sections"] = {row["student_id"]: row["student_id"] for row in registrations}
        inputs["teaching"] = [
            {"teacher_id": "T0", "course_code": code, "section_id": f"{code}X"}
            for code in ["A", "B"]
        ]
        plan = schedule_papers(
            [{"course_code": code} for code in ["A", "B"]], registrations,
            settings("2026-11-02", "2026-11-02", ["Mon"]), {}, **inputs,
        )
        # T0 must supervise both papers. Single-paper rooms cannot put them in
        # both rooms in one slot; each paper must move to its own session.
        self.assertEqual(len(plan.slots), 2)
        self.assertTrue(all(len(slot.rooms) == 2 for slot in plan.slots.values()))
        self.assertTrue(all(any("T0" in r.teachers for r in s.rooms) for s in plan.slots.values()))

    def test_does_not_prune_a_partial_slot_that_later_mixing_can_rescue(self):
        registrations = [
            {"student_id": f"{code}{i:02}", "course_code": code}
            for code, count in [("A", 13), ("B", 9), ("C", 1)] for i in range(count)
        ]
        inputs = resources(registrations)
        inputs["rooms"] = [
            {"room_id": f"S{i}", "rows": 6, "seat_columns": 3} for i in range(3)
        ]
        inputs["teachers"] = [{"teacher_id": f"T{i}", "rank": "PHD"} for i in range(4)]
        plan = schedule_papers(
            [{"course_code": code} for code in ["A", "B", "C"]], registrations,
            settings("2026-11-02", "2026-11-02", ["Mon"]), {}, **inputs,
        )
        # A+B can be seated separately in three rooms but cannot staff them.
        # Adding C runs out of separate rooms, allowing mixing into two rooms.
        self.assertEqual(len(plan.slots), 1)
        self.assertEqual(len(next(iter(plan.slots.values())).rooms), 2)


if __name__ == "__main__":
    unittest.main()

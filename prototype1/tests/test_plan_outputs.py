"""Check exported plans against inputs, independently of the planning helpers."""

import csv
from datetime import date
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def run_cli(dataset, output):
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / "main.py"), str(dataset), "--output", str(output)],
        capture_output=True, text=True, timeout=20,
    )


class PlanOutputTests(unittest.TestCase):
    def check_plan(self, dataset, output):
        settings = yaml.safe_load((dataset / "settings.yaml").read_text())
        groups = yaml.safe_load((dataset / "constraints.yaml").read_text())["same_paper"]
        courses = read_csv(dataset / "courses.csv")
        code_to_paper = {row["course_code"]: row["course_code"] for row in courses}
        for group in groups:
            code_to_paper.update({code: group[0] for code in group})
        sections = {
            student["student_id"]: section["section_id"]
            for section in read_csv(dataset / "sections.csv")
            for student in read_csv(dataset / "sections" / f"{section['section_id']}.csv")
        }
        registrations = read_csv(dataset / "registrations.csv")
        expected = {}
        for row in registrations:
            expected.setdefault(code_to_paper[row["course_code"]], set()).add(row["student_id"])
        own = {}
        for assignment in read_csv(dataset / "teaching.csv"):
            paper = code_to_paper[assignment["course_code"]]
            own.setdefault((assignment["teacher_id"], paper), set()).update(
                row["student_id"] for row in registrations
                if row["course_code"] == assignment["course_code"]
                and sections[row["student_id"]] == assignment["section_id"]
            )
        rooms = read_csv(dataset / "rooms.csv")
        room_ids = [room["room_id"] for room in rooms]
        room_by_id = {room["room_id"]: room for room in rooms}
        ranks = {row["teacher_id"]: row["rank"] for row in read_csv(dataset / "teachers.csv")}
        schedule = read_csv(output / "schedule.csv")
        duties = read_csv(output / "duties.csv")
        self.assertEqual(len(schedule), len(expected))
        self.assertEqual({row["paper_id"] for row in schedule}, set(expected))
        seen_students = {paper: [] for paper in expected}
        dates_by_student = {}
        slot_papers = {}
        for row in schedule:
            exam_date = date.fromisoformat(row["date"])
            self.assertGreaterEqual(exam_date, date.fromisoformat(str(settings["start_date"])))
            self.assertLessEqual(exam_date, date.fromisoformat(str(settings["end_date"])))
            self.assertIn(exam_date.strftime("%a"), settings["exam_weekdays"])
            self.assertNotIn(exam_date.isoformat(), [str(day) for day in settings["holidays"]])
            self.assertIn(row["session"], settings["sessions"])
            self.assertEqual(set(row["students"].split(";")), expected[row["paper_id"]])
            self.assertEqual(
                set(row["course_codes"].split(";")),
                {code for code, paper in code_to_paper.items() if paper == row["paper_id"]},
            )
            slot_papers.setdefault((row["date"], row["session"]), set()).add(row["paper_id"])
            for student in expected[row["paper_id"]]:
                dates_by_student.setdefault(student, []).append(exam_date)
        for dates in dates_by_student.values():
            dates.sort()
            self.assertTrue(all((b - a).days >= settings["min_gap_days"] for a, b in zip(dates, dates[1:])))

        duties_by_room = {}
        teachers_by_slot = {}
        for duty in duties:
            self.assertIn(duty["teacher_id"], ranks)
            slot = (duty["date"], duty["session"])
            self.assertIn(slot, slot_papers)
            self.assertNotIn(duty["teacher_id"], teachers_by_slot.setdefault(slot, set()))
            teachers_by_slot[slot].add(duty["teacher_id"])
            duties_by_room.setdefault((*slot, duty["room_id"]), []).append(duty["teacher_id"])

        supervised = set()
        expected_files = {Path("schedule.csv"), Path("duties.csv")}
        for slot, papers in slot_papers.items():
            seating_dir = output / "daywise_seating_plans" / slot[0] / slot[1]
            files = {file.stem: file for file in seating_dir.glob("*.csv")}
            self.assertEqual(set(files), set(room_ids[:len(files)]))
            for room_id in room_ids[:len(files)]:
                room = room_by_id[room_id]
                file = files[room_id]
                expected_files.add(file.relative_to(output))
                with file.open(newline="", encoding="utf-8") as stream:
                    grid = list(csv.reader(stream))
                self.assertEqual(len(grid), int(room["rows"]))
                self.assertTrue(all(len(row) == int(room["seat_columns"]) for row in grid))
                columns = [{cell.split(":", 1)[0] for cell in col if cell} for col in zip(*grid)]
                self.assertTrue(all(len(column) <= 1 for column in columns))
                self.assertTrue(all(not (a & b) for a, b in zip(columns, columns[1:])))
                room_students = [cell.split(":", 1) for col in zip(*grid) for cell in col if cell]
                self.assertTrue(room_students)
                assigned = duties_by_room.pop((*slot, room_id))
                self.assertEqual(len(assigned), settings["invigilators_per_room"])
                for paper, student in room_students:
                    self.assertIn(paper, papers)
                    self.assertIn(student, expected[paper])
                    seen_students[paper].append(student)
                    for teacher in assigned:
                        self.assertNotIn(student, own.get((teacher, paper), set()))
                        supervised.add((teacher, paper))
        self.assertFalse(duties_by_room)
        for paper, students in seen_students.items():
            self.assertEqual(students, sorted(expected[paper]))
        for pair, students in own.items():
            teacher, paper = pair
            if ranks[teacher] != "PHD" and students != expected[paper]:
                self.assertIn(pair, supervised)
        self.assertEqual({file.relative_to(output) for file in output.rglob("*") if file.is_file()}, expected_files)

    def test_bundled_datasets_export_valid_deterministic_complete_plans(self):
        for name in ["tiny", "main"]:
            with self.subTest(dataset=name), tempfile.TemporaryDirectory() as directory:
                dataset = ROOT / "data" / name
                output = Path(directory)
                first = run_cli(dataset, output / "first")
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                first_plan = next((output / "first").iterdir())
                self.check_plan(dataset, first_plan)
                second = run_cli(dataset, output / "second")
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                second_plan = next((output / "second").iterdir())
                for file in first_plan.rglob("*"):
                    if file.is_file():
                        self.assertEqual(file.read_bytes(), (second_plan / file.relative_to(first_plan)).read_bytes())

    def test_impossible_teacher_pool_writes_only_reason_and_exits_two(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "input"
            shutil.copytree(ROOT / "data" / "tiny", dataset)
            (dataset / "teachers.csv").write_text("teacher_id,rank\nT001,PHD\n")
            result = run_cli(dataset, root / "output")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            files = [file for file in (root / "output").rglob("*") if file.is_file()]
            self.assertEqual([file.name for file in files], ["why.txt"])
            reason = files[0].read_text()
            self.assertIn("Rule: invigilators", reason)
            self.assertIn(reason.strip(), result.stdout)

    def test_invalid_input_exits_one_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_cli(root / "missing", root / "output")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Input invalid", result.stdout)
            self.assertFalse((root / "output").exists())

    def test_impossible_column_capacity_writes_no_partial_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "input"
            shutil.copytree(ROOT / "data" / "tiny", dataset)
            (dataset / "rooms.csv").write_text("room_id,type,rows,seat_columns\nS01,S,6,3\n")
            result = run_cli(dataset, root / "output")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            files = [file for file in (root / "output").rglob("*") if file.is_file()]
            self.assertEqual([file.name for file in files], ["why.txt"])
            self.assertIn("column rule allows at most 12", files[0].read_text())

    def test_cli_reports_all_sections_exemption_and_keeps_teacher_out_of_own_room(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "input"
            shutil.copytree(ROOT / "data" / "tiny", dataset)
            (dataset / "teaching.csv").write_text(
                "teacher_id,course_code,section_id\nT001,AIM1101,AIML1_I\n"
            )
            result = run_cli(dataset, root / "output")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Exemption: T001 need not invigilate AIM1101", result.stdout)
            self.check_plan(dataset, next((root / "output").iterdir()))


if __name__ == "__main__":
    unittest.main()

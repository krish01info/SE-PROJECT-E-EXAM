from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import yaml

from scheduler import ExamPlan, NoScheduleError, schedule_papers
from validation import validate_input


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Prototype 1 exam plan from an input folder.")
    parser.add_argument("input_dir", type=Path, help="Folder containing the Prototype 1 input files.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output root for the complete exam plan (default: output/).",
    )
    return parser.parse_args()


def _read_csv(input_dir: Path, filename: str) -> list[dict[str, str]]:
    with (input_dir / filename).open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _load_schedule_inputs(input_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict, dict]:
    with (input_dir / "settings.yaml").open(encoding="utf-8") as file:
        settings = yaml.safe_load(file)
    with (input_dir / "constraints.yaml").open(encoding="utf-8") as file:
        constraints = yaml.safe_load(file)
    return (
        _read_csv(input_dir, "courses.csv"),
        _read_csv(input_dir, "registrations.csv"),
        settings,
        constraints,
    )


def _write_schedule(output_dir: Path, schedule: list[dict]) -> None:
    with (output_dir / "schedule.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["date", "session", "paper_id", "course_codes", "students"],
        )
        writer.writeheader()
        for row in schedule:
            writer.writerow(
                {
                    "date": row["date"].isoformat(),
                    "session": row["session"],
                    "paper_id": row["paper_id"],
                    "course_codes": ";".join(row["course_codes"]),
                    "students": ";".join(row["students"]),
                }
            )


def _write_plan(output_dir: Path, plan: ExamPlan) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_schedule(output_dir, plan.schedule)
    with (output_dir / "duties.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "session", "room_id", "teacher_id"])
        for (exam_date, session), slot in plan.slots.items():
            seating_dir = output_dir / "daywise_seating_plans" / exam_date.isoformat() / session
            seating_dir.mkdir(parents=True)
            for room in slot.rooms:
                for teacher in room.teachers:
                    writer.writerow([exam_date.isoformat(), session, room.room_id, teacher])
                with (seating_dir / f"{room.room_id}.csv").open("w", newline="", encoding="utf-8") as room_file:
                    csv.writer(room_file).writerows(
                        [f"{cell[0]}:{cell[1]}" if cell else "" for cell in row]
                        for row in room.seats
                    )


def _student_sections(input_dir: Path) -> dict[str, str]:
    return {
        student["student_id"].strip(): section["section_id"].strip()
        for section in _read_csv(input_dir, "sections.csv")
        for student in _read_csv(input_dir, f"sections/{section['section_id'].strip()}.csv")
    }


def _new_output_dir(output_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    candidate = output_root / timestamp
    suffix = 1
    while candidate.exists():
        candidate = output_root / f"{timestamp}_{suffix:02d}"
        suffix += 1
    return candidate


def main() -> int:
    args = parse_args()
    result = validate_input(args.input_dir)

    if not result.valid:
        print("Input invalid.")
        for error in result.errors:
            print(f"- {error}")
        return 1

    print("Input valid.")
    print(
        f"{result.students} students, "
        f"{result.course_codes} course codes, "
        f"{result.rooms} rooms, "
        f"{result.invigilators} invigilators."
    )

    courses, registrations, settings, constraints = _load_schedule_inputs(args.input_dir)
    try:
        plan = schedule_papers(
            courses, registrations, settings, constraints,
            rooms=_read_csv(args.input_dir, "rooms.csv"),
            teachers=_read_csv(args.input_dir, "teachers.csv"),
            teaching=_read_csv(args.input_dir, "teaching.csv"),
            student_sections=_student_sections(args.input_dir),
        )
    except NoScheduleError as exc:
        output_dir = _new_output_dir(args.output)
        output_dir.mkdir(parents=True)
        (output_dir / "why.txt").write_text(f"{exc}\n", encoding="utf-8")
        print(exc)
        print(f"Reason saved to {output_dir / 'why.txt'}")
        return 2

    output_dir = _new_output_dir(args.output)
    _write_plan(output_dir, plan)
    for slot in plan.slots.values():
        for teacher, paper in slot.exemptions:
            print(
                f"Exemption: {teacher} need not invigilate {paper}: "
                "they teach every section writing it; own-student duties remain forbidden."
            )
    print(f"Exam plan written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

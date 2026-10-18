from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


CSV_HEADERS = {
    "sections.csv": ["section_id", "cohort_id", "program", "year"],
    "courses.csv": ["course_code", "title", "cohort_id", "kind"],
    "registrations.csv": ["student_id", "course_code"],
    "rooms.csv": ["room_id", "type", "rows", "seat_columns"],
    "teachers.csv": ["teacher_id", "rank"],
    "teaching.csv": ["teacher_id", "course_code", "section_id"],
}

REQUIRED_YAML = ["settings.yaml", "constraints.yaml"]
VALID_COURSE_KINDS = {"CORE", "ELECTIVE"}
VALID_ROOM_TYPES = {"S", "M"}
VALID_RANKS = {"PROF", "ASSOC", "ASST", "PHD"}
VALID_WEEKDAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


@dataclass
class ValidationResult:
    errors: list[str]
    students: int = 0
    course_codes: int = 0
    rooms: int = 0
    invigilators: int = 0

    @property
    def valid(self) -> bool:
        return not self.errors


def _error(filename: str, message: str, row: int | None = None) -> str:
    if row is None:
        return f"{filename}: {message}"
    return f"{filename} row {row}: {message}"


def _read_csv(input_dir: Path, filename: str, errors: list[str]) -> list[dict[str, str]] | None:
    path = input_dir / filename
    if not path.is_file():
        errors.append(_error(filename, "file is missing"))
        return None

    try:
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            actual_header = reader.fieldnames or []
            expected_header = CSV_HEADERS[filename]
            if actual_header != expected_header:
                errors.append(
                    _error(
                        filename,
                        f"header must be {','.join(expected_header)}; found {','.join(actual_header)}",
                    )
                )
                return None
            return list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(_error(filename, f"could not be read: {exc}"))
        return None


def _read_yaml(input_dir: Path, filename: str, errors: list[str]) -> dict[str, Any] | None:
    path = input_dir / filename
    if not path.is_file():
        errors.append(_error(filename, "file is missing"))
        return None

    try:
        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        errors.append(_error(filename, f"could not be read as YAML: {exc}"))
        return None

    if not isinstance(data, dict):
        errors.append(_error(filename, "top level must be a mapping"))
        return None
    return data


def _blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _positive_int(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 1
    if isinstance(value, str):
        try:
            return int(value) >= 1 and str(int(value)) == value.strip()
        except ValueError:
            return False
    return False


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_unique_key(
    filename: str,
    rows: list[dict[str, str]] | None,
    key: str,
    errors: list[str],
) -> set[str] | None:
    if rows is None:
        return None

    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        value = row.get(key, "").strip()
        if not value:
            errors.append(_error(filename, f"{key} must not be blank", row_number))
        elif value in seen:
            errors.append(_error(filename, f"duplicate {key} {value}", row_number))
        else:
            seen.add(value)
    return seen


def _validate_settings(settings: dict[str, Any] | None, errors: list[str]) -> None:
    if settings is None:
        return

    required = [
        "start_date",
        "end_date",
        "exam_weekdays",
        "holidays",
        "sessions",
        "min_gap_days",
        "invigilators_per_room",
    ]
    for key in required:
        if key not in settings:
            errors.append(_error("settings.yaml", f"missing key {key}"))

    start = _parse_date(settings.get("start_date"))
    end = _parse_date(settings.get("end_date"))
    if "start_date" in settings and start is None:
        errors.append(_error("settings.yaml", "start_date must be a valid YYYY-MM-DD date"))
    if "end_date" in settings and end is None:
        errors.append(_error("settings.yaml", "end_date must be a valid YYYY-MM-DD date"))
    if start is not None and end is not None and start > end:
        errors.append(_error("settings.yaml", "start_date must be on or before end_date"))

    weekdays = settings.get("exam_weekdays")
    if "exam_weekdays" in settings:
        if not isinstance(weekdays, list) or not weekdays:
            errors.append(_error("settings.yaml", "exam_weekdays must be a non-empty list"))
        else:
            for weekday in weekdays:
                if weekday not in VALID_WEEKDAYS:
                    errors.append(_error("settings.yaml", f"invalid exam weekday {weekday}"))

    holidays = settings.get("holidays")
    if "holidays" in settings:
        if not isinstance(holidays, list):
            errors.append(_error("settings.yaml", "holidays must be a list"))
        else:
            for value in holidays:
                if _parse_date(value) is None:
                    errors.append(_error("settings.yaml", f"invalid holiday date {value}"))

    sessions = settings.get("sessions")
    if "sessions" in settings:
        if not isinstance(sessions, list) or len(sessions) != 2:
            errors.append(_error("settings.yaml", "sessions must contain exactly two entries"))
        elif any(not isinstance(value, str) or not value.strip() for value in sessions):
            errors.append(_error("settings.yaml", "session names must be non-blank strings"))
        elif len(set(sessions)) != 2:
            errors.append(_error("settings.yaml", "session names must be different"))

    for key in ("min_gap_days", "invigilators_per_room"):
        if key in settings and not _positive_int(settings.get(key)):
            errors.append(_error("settings.yaml", f"{key} must be a whole number of at least 1"))


def _validate_constraints(
    constraints: dict[str, Any] | None,
    course_codes: set[str] | None,
    errors: list[str],
) -> None:
    if constraints is None:
        return

    groups = constraints.get("same_paper", [])
    if not isinstance(groups, list):
        errors.append(_error("constraints.yaml", "same_paper must be a list"))
        return

    used_codes: set[str] = set()
    for group_number, group in enumerate(groups, start=1):
        if not isinstance(group, list) or len(group) < 2:
            errors.append(
                _error("constraints.yaml", f"same_paper group {group_number} must contain at least two codes")
            )
            continue

        for code in group:
            if not isinstance(code, str) or not code.strip():
                errors.append(
                    _error("constraints.yaml", f"same_paper group {group_number} contains a blank code")
                )
                continue
            if code in used_codes:
                errors.append(_error("constraints.yaml", f"course code {code} appears in more than one same_paper group"))
            else:
                used_codes.add(code)
            if course_codes is not None and code not in course_codes:
                errors.append(_error("constraints.yaml", f"course code {code} is not in courses.csv"))


def validate_input(input_dir: Path) -> ValidationResult:
    errors: list[str] = []

    if not input_dir.exists():
        return ValidationResult([f"{input_dir}: input directory does not exist"])
    if not input_dir.is_dir():
        return ValidationResult([f"{input_dir}: input path is not a directory"])

    tables = {
        filename: _read_csv(input_dir, filename, errors)
        for filename in CSV_HEADERS
    }
    settings = _read_yaml(input_dir, "settings.yaml", errors)
    constraints = _read_yaml(input_dir, "constraints.yaml", errors)

    sections = tables["sections.csv"]
    courses = tables["courses.csv"]
    registrations = tables["registrations.csv"]
    rooms = tables["rooms.csv"]
    teachers = tables["teachers.csv"]
    teaching = tables["teaching.csv"]

    section_ids = _validate_unique_key("sections.csv", sections, "section_id", errors)
    course_codes = _validate_unique_key("courses.csv", courses, "course_code", errors)
    room_ids = _validate_unique_key("rooms.csv", rooms, "room_id", errors)
    teacher_ids = _validate_unique_key("teachers.csv", teachers, "teacher_id", errors)
    del room_ids  # uniqueness is the only room-id check needed at this step

    if sections is not None:
        for row_number, row in enumerate(sections, start=2):
            for key in ("cohort_id", "program", "year"):
                if _blank(row.get(key)):
                    errors.append(_error("sections.csv", f"{key} must not be blank", row_number))
            if not _blank(row.get("year")) and not _positive_int(row["year"]):
                errors.append(_error("sections.csv", "year must be a positive whole number", row_number))

    cohort_by_course: dict[str, str] = {}
    if courses is not None:
        for row_number, row in enumerate(courses, start=2):
            code = row.get("course_code", "").strip()
            title = row.get("title", "").strip()
            cohort = row.get("cohort_id", "").strip()
            kind = row.get("kind", "").strip()
            if not title:
                errors.append(_error("courses.csv", "title must not be blank", row_number))
            if not cohort:
                errors.append(_error("courses.csv", "cohort_id must not be blank", row_number))
            if kind not in VALID_COURSE_KINDS:
                errors.append(_error("courses.csv", f"kind must be CORE or ELECTIVE; found {kind or '<blank>'}", row_number))
            if code:
                cohort_by_course[code] = cohort

    if rooms is not None:
        for row_number, row in enumerate(rooms, start=2):
            room_type = row.get("type", "").strip()
            if room_type not in VALID_ROOM_TYPES:
                errors.append(_error("rooms.csv", f"type must be S or M; found {room_type or '<blank>'}", row_number))
            dimensions_valid = True
            for key in ("rows", "seat_columns"):
                if not _positive_int(row.get(key)):
                    errors.append(_error("rooms.csv", f"{key} must be a positive whole number", row_number))
                    dimensions_valid = False
            if room_type in VALID_ROOM_TYPES and dimensions_valid:
                actual_shape = (int(row["rows"]), int(row["seat_columns"]))
                expected_shape = {"S": (6, 3), "M": (7, 6)}[room_type]
                if actual_shape != expected_shape:
                    errors.append(
                        _error(
                            "rooms.csv",
                            f"type {room_type} must have rows={expected_shape[0]} and seat_columns={expected_shape[1]}",
                            row_number,
                        )
                    )

    if teachers is not None:
        for row_number, row in enumerate(teachers, start=2):
            rank = row.get("rank", "").strip()
            if rank not in VALID_RANKS:
                errors.append(
                    _error(
                        "teachers.csv",
                        f"rank must be PROF, ASSOC, ASST or PHD; found {rank or '<blank>'}",
                        row_number,
                    )
                )

    student_to_section: dict[str, str] = {}
    section_to_students: dict[str, set[str]] = {}
    if sections is not None:
        sections_dir = input_dir / "sections"
        if not sections_dir.is_dir():
            errors.append(_error("sections/", "directory is missing"))
        else:
            for row in sections:
                section_id = row.get("section_id", "").strip()
                if not section_id:
                    continue
                roster_filename = f"sections/{section_id}.csv"
                roster_path = input_dir / roster_filename
                if not roster_path.is_file():
                    errors.append(_error(roster_filename, "file is missing"))
                    continue
                try:
                    with roster_path.open(newline="", encoding="utf-8") as file:
                        reader = csv.DictReader(file)
                        header = reader.fieldnames or []
                        if header != ["student_id"]:
                            errors.append(
                                _error(roster_filename, f"header must be student_id; found {','.join(header)}")
                            )
                            continue
                        roster_rows = list(reader)
                except (OSError, UnicodeError, csv.Error) as exc:
                    errors.append(_error(roster_filename, f"could not be read: {exc}"))
                    continue

                students_here: set[str] = set()
                for row_number, roster_row in enumerate(roster_rows, start=2):
                    student_id = roster_row.get("student_id", "").strip()
                    if not student_id:
                        errors.append(_error(roster_filename, "student_id must not be blank", row_number))
                        continue
                    if student_id in students_here:
                        errors.append(_error(roster_filename, f"duplicate student_id {student_id}", row_number))
                        continue
                    students_here.add(student_id)
                    if student_id in student_to_section:
                        errors.append(
                            _error(
                                roster_filename,
                                f"student_id {student_id} already appears in section {student_to_section[student_id]}",
                                row_number,
                            )
                        )
                    else:
                        student_to_section[student_id] = section_id
                section_to_students[section_id] = students_here

    cohort_by_section: dict[str, str] = {}
    if sections is not None:
        for row in sections:
            section_id = row.get("section_id", "").strip()
            if section_id:
                cohort_by_section[section_id] = row.get("cohort_id", "").strip()

    registration_pairs: set[tuple[str, str]] = set()
    registrations_by_student: dict[str, set[str]] = {}
    registrations_by_course: dict[str, set[str]] = {}
    if registrations is not None:
        for row_number, row in enumerate(registrations, start=2):
            student_id = row.get("student_id", "").strip()
            course_code = row.get("course_code", "").strip()
            if not student_id:
                errors.append(_error("registrations.csv", "student_id must not be blank", row_number))
            if not course_code:
                errors.append(_error("registrations.csv", "course_code must not be blank", row_number))
            if not student_id or not course_code:
                continue

            pair = (student_id, course_code)
            if pair in registration_pairs:
                errors.append(_error("registrations.csv", f"duplicate registration {student_id},{course_code}", row_number))
            else:
                registration_pairs.add(pair)

            student_exists = not student_to_section or student_id in student_to_section
            if student_to_section and student_id not in student_to_section:
                errors.append(_error("registrations.csv", f"student_id {student_id} is not in any section roster", row_number))
                student_exists = False
            if course_codes is not None and course_code not in course_codes:
                errors.append(_error("registrations.csv", f"course code {course_code} is not in courses.csv", row_number))

            if student_exists:
                registrations_by_student.setdefault(student_id, set()).add(course_code)
                registrations_by_course.setdefault(course_code, set()).add(student_id)

            if (
                student_to_section
                and course_codes is not None
                and student_id in student_to_section
                and course_code in cohort_by_course
            ):
                student_section = student_to_section[student_id]
                student_cohort = cohort_by_section.get(student_section)
                course_cohort = cohort_by_course.get(course_code)
                if student_cohort and course_cohort and student_cohort != course_cohort:
                    errors.append(
                        _error(
                            "registrations.csv",
                            f"student {student_id} belongs to {student_cohort} but course {course_code} belongs to {course_cohort}",
                            row_number,
                        )
                    )

    if registrations is not None and student_to_section:
        for student_id in sorted(student_to_section):
            if student_id not in registrations_by_student:
                errors.append(_error("registrations.csv", f"student {student_id} has no registration"))

    if registrations is not None and course_codes is not None:
        for course_code in sorted(course_codes):
            if course_code not in registrations_by_course:
                errors.append(_error("registrations.csv", f"course code {course_code} has no registrations"))

    if teaching is not None:
        seen_teaching: set[tuple[str, str, str]] = set()
        for row_number, row in enumerate(teaching, start=2):
            teacher_id = row.get("teacher_id", "").strip()
            course_code = row.get("course_code", "").strip()
            section_id = row.get("section_id", "").strip()

            for key, value in (
                ("teacher_id", teacher_id),
                ("course_code", course_code),
                ("section_id", section_id),
            ):
                if not value:
                    errors.append(_error("teaching.csv", f"{key} must not be blank", row_number))
            if not teacher_id or not course_code or not section_id:
                continue

            triple = (teacher_id, course_code, section_id)
            if triple in seen_teaching:
                errors.append(_error("teaching.csv", f"duplicate teaching row {teacher_id},{course_code},{section_id}", row_number))
            else:
                seen_teaching.add(triple)

            if teacher_ids is not None and teacher_id not in teacher_ids:
                errors.append(_error("teaching.csv", f"teacher_id {teacher_id} is not in teachers.csv", row_number))
            if course_codes is not None and course_code not in course_codes:
                errors.append(_error("teaching.csv", f"course code {course_code} is not in courses.csv", row_number))
            if section_ids is not None and section_id not in section_ids:
                errors.append(_error("teaching.csv", f"section_id {section_id} is not in sections.csv", row_number))

            if course_code in cohort_by_course and section_id in cohort_by_section:
                course_cohort = cohort_by_course[course_code]
                section_cohort = cohort_by_section[section_id]
                if course_cohort != section_cohort:
                    errors.append(
                        _error(
                            "teaching.csv",
                            f"course {course_code} belongs to {course_cohort} but section {section_id} belongs to {section_cohort}",
                            row_number,
                        )
                    )
                elif registrations is not None and section_id in section_to_students:
                    students = section_to_students[section_id]
                    if not any((student_id, course_code) in registration_pairs for student_id in students):
                        errors.append(
                            _error(
                                "teaching.csv",
                                f"no student in section {section_id} is registered for {course_code}",
                                row_number,
                            )
                        )

    _validate_settings(settings, errors)
    _validate_constraints(constraints, course_codes, errors)

    return ValidationResult(
        errors=errors,
        students=len(student_to_section),
        course_codes=len(course_codes or set()),
        rooms=len(rooms or []),
        invigilators=len(teacher_ids or set()),
    )

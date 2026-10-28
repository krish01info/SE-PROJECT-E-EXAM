"""Check an input folder against data_design_spec.md section 3.

This module only CHECKS. Reading is loader.py's job.

It runs in two stages (decided in step 3, option (a)):

  Stage 1, check_files(): every file is present and readable, every CSV
  header is right, every row has as many values as the header, and both
  YAML files are valid YAML. If anything fails here, stage 2 does not run,
  because one broken file would cause hundreds of fake follow-on errors.

  Stage 2, check_data(): the rules about what is inside the files: IDs,
  references between files, registrations, settings and constraints.

Both stages collect EVERY problem instead of stopping at the first one.
format_report() prints them grouped by rule, with a count above each group,
and still lists every single problem with its file and row.
"""

import csv
import datetime
from dataclasses import dataclass
from pathlib import Path

import yaml

import loader

COURSE_KINDS = ["CORE", "ELECTIVE"]
ROOM_TYPES = ["S", "M"]
TEACHER_RANKS = ["PROF", "ASSOC", "ASST", "PHD"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SETTING_KEYS = [
    "start_date", "end_date", "exam_weekdays", "holidays",
    "sessions", "min_gap_days", "invigilators_per_room",
]


@dataclass
class Problem:
    file: str          # e.g. "registrations.csv" or "sections/BT2CSE_I.csv"
    row: int | None    # line number in the file, or None for the whole file
    rule: str          # short name of the broken rule; used for grouping
    message: str       # what exactly is wrong

    def __str__(self):
        if self.row is None:
            return f"{self.file}: {self.message}"
        return f"{self.file} row {self.row}: {self.message}"


# ---------------------------------------------------------------- report

def format_report(problems):
    """Text listing every problem, grouped by rule, groups in the order
    they were first found."""
    groups = {}
    for problem in problems:
        groups.setdefault(problem.rule, []).append(problem)

    lines = [f"Input is invalid: {len(problems)} problem(s), "
             f"{len(groups)} rule(s) broken."]
    for rule, group in groups.items():
        lines.append("")
        lines.append(f"[{rule}] {len(group)} problem(s)")
        lines.extend(f"  {problem}" for problem in group)
    return "\n".join(lines)


# ---------------------------------------------------------------- stage 1

def check_csv_file(path, file_label, expected_columns, problems):
    """Stage 1 checks for one CSV file."""
    if not path.is_file():
        problems.append(Problem(file_label, None, "file is present",
                                "file is missing"))
        return
    try:
        header, rows = loader.read_csv_lines(path)
    except (UnicodeDecodeError, csv.Error) as error:
        problems.append(Problem(file_label, None, "file is readable",
                                f"cannot be read as UTF-8 CSV ({error})"))
        return
    if header != expected_columns:
        found = ",".join(header) if header else "(empty file)"
        problems.append(Problem(
            file_label, 1, "header matches",
            f"header should be {','.join(expected_columns)}, found {found}"))
        return
    for row_number, values in rows:
        if len(values) != len(expected_columns):
            problems.append(Problem(
                file_label, row_number, "row has one value per column",
                f"has {len(values)} value(s), expected {len(expected_columns)}"))


def check_files(input_dir):
    """Stage 1. Returns a list of Problems; empty means stage 2 can run."""
    input_dir = Path(input_dir)
    problems = []
    if not input_dir.is_dir():
        problems.append(Problem(str(input_dir), None, "input folder exists",
                                "folder not found"))
        return problems

    for file_name, columns in loader.CSV_COLUMNS.items():
        check_csv_file(input_dir / file_name, file_name, columns, problems)

    if not (input_dir / loader.ROSTER_FOLDER).is_dir():
        problems.append(Problem(f"{loader.ROSTER_FOLDER}/", None,
                                "file is present", "folder is missing"))
    else:
        for path in loader.roster_paths(input_dir):
            check_csv_file(path, f"{loader.ROSTER_FOLDER}/{path.name}",
                           loader.ROSTER_COLUMNS, problems)

    for file_name in loader.YAML_FILES:
        path = input_dir / file_name
        if not path.is_file():
            problems.append(Problem(file_name, None, "file is present",
                                    "file is missing"))
            continue
        try:
            content = loader.read_yaml(path)
        except (UnicodeDecodeError, yaml.YAMLError) as error:
            problems.append(Problem(file_name, None, "file is valid YAML",
                                    f"cannot be read as YAML ({error})"))
            continue
        if not isinstance(content, dict):
            problems.append(Problem(file_name, None, "file is valid YAML",
                                    "should be a list of `key: value` lines"))
    return problems


# ---------------------------------------------------------------- stage 2

def check_ids(rows, file_name, id_column, problems):
    """IDs are never blank and unique. Returns {id: row} of the good rows."""
    by_id = {}
    for row in rows:
        value = row[id_column]
        if value == "":
            problems.append(Problem(file_name, row["_row"], "ID is not blank",
                                    f"{id_column} is blank"))
        elif value in by_id:
            problems.append(Problem(
                file_name, row["_row"], "ID is unique",
                f"{id_column} {value} is already used in row {by_id[value]['_row']}"))
        else:
            by_id[value] = row
    return by_id


def is_positive_whole_number(text):
    return text.isdigit() and int(text) >= 1


def check_sections(data, problems):
    """sections.csv and the roster files in sections/.
    Returns (sections, section_of, first_seen): section_of maps
    student -> section, first_seen maps student -> (file, row)."""
    sections = check_ids(data["sections"], "sections.csv", "section_id", problems)
    for row in sections.values():
        if row["cohort_id"] == "":
            problems.append(Problem("sections.csv", row["_row"],
                                    "ID is not blank", "cohort_id is blank"))

    for section_id, row in sections.items():
        if section_id not in data["roster_files"]:
            problems.append(Problem(
                "sections.csv", row["_row"], "section has a roster file",
                f"section {section_id} has no file "
                f"{loader.ROSTER_FOLDER}/{section_id}.csv"))
    for section_id in data["roster_files"]:
        if section_id not in sections:
            problems.append(Problem(
                f"{loader.ROSTER_FOLDER}/{section_id}.csv", None,
                "roster file is listed in sections.csv",
                f"section {section_id} is not in sections.csv"))

    # Every student appears in exactly one section file (first one wins).
    section_of = {}
    first_seen = {}
    for student in data["students"]:
        student_id = student["student_id"]
        if student_id == "":
            problems.append(Problem(student["_file"], student["_row"],
                                    "ID is not blank", "student_id is blank"))
        elif student_id in section_of:
            file_name, row_number = first_seen[student_id]
            problems.append(Problem(
                student["_file"], student["_row"],
                "student is in exactly one section",
                f"student {student_id} is already in {file_name} row {row_number}"))
        else:
            section_of[student_id] = student["section_id"]
            first_seen[student_id] = (student["_file"], student["_row"])
    return sections, section_of, first_seen


def check_courses(data, sections, problems):
    courses = check_ids(data["courses"], "courses.csv", "course_code", problems)
    cohorts = {row["cohort_id"] for row in sections.values()}
    for code, row in courses.items():
        if row["cohort_id"] not in cohorts:
            problems.append(Problem(
                "courses.csv", row["_row"], "cohort exists",
                f"cohort {row['cohort_id'] or '(blank)'} of {code} "
                f"has no section in sections.csv"))
        if row["kind"] not in COURSE_KINDS:
            problems.append(Problem(
                "courses.csv", row["_row"], "kind is CORE or ELECTIVE",
                f"kind of {code} is {row['kind'] or '(blank)'}"))
    return courses


def check_rooms(data, problems):
    rooms = check_ids(data["rooms"], "rooms.csv", "room_id", problems)
    for room_id, row in rooms.items():
        if row["type"] not in ROOM_TYPES:
            problems.append(Problem(
                "rooms.csv", row["_row"], "room type is S or M",
                f"type of {room_id} is {row['type'] or '(blank)'}"))
        for column in ["rows", "seat_columns"]:
            if not is_positive_whole_number(row[column]):
                problems.append(Problem(
                    "rooms.csv", row["_row"],
                    "rows and seat_columns are positive whole numbers",
                    f"{column} of {room_id} is {row[column] or '(blank)'}"))
    return rooms


def check_teachers(data, problems):
    teachers = check_ids(data["teachers"], "teachers.csv", "teacher_id", problems)
    for teacher_id, row in teachers.items():
        if row["rank"] not in TEACHER_RANKS:
            problems.append(Problem(
                "teachers.csv", row["_row"], "rank is PROF, ASSOC, ASST or PHD",
                f"rank of {teacher_id} is {row['rank'] or '(blank)'}"))
    return teachers


def check_registrations(data, sections, section_of, first_seen, courses,
                        problems):
    """registrations.csv. Returns the set of (section_id, course_code) pairs
    that have at least one student, for the teaching.csv check."""
    seen_pairs = {}
    students_with_registration = set()
    codes_with_registration = set()
    section_codes = set()

    for row in data["registrations"]:
        student_id, code = row["student_id"], row["course_code"]
        known_student = student_id in section_of
        known_code = code in courses
        if not known_student:
            problems.append(Problem(
                "registrations.csv", row["_row"], "student exists",
                f"student {student_id or '(blank)'} is not in any section file"))
        if not known_code:
            problems.append(Problem(
                "registrations.csv", row["_row"], "course code exists",
                f"course code {code or '(blank)'} is not in courses.csv"))
        if not (known_student and known_code):
            continue

        if (student_id, code) in seen_pairs:
            problems.append(Problem(
                "registrations.csv", row["_row"], "no duplicate registrations",
                f"{student_id} {code} is already in row "
                f"{seen_pairs[(student_id, code)]}"))
            continue
        seen_pairs[(student_id, code)] = row["_row"]

        section_id = section_of[student_id]
        if section_id in sections:  # unlisted roster files are reported above
            student_cohort = sections[section_id]["cohort_id"]
            course_cohort = courses[code]["cohort_id"]
            if student_cohort != course_cohort:
                problems.append(Problem(
                    "registrations.csv", row["_row"],
                    "student registers only for own cohort's codes",
                    f"{student_id} is in cohort {student_cohort}, but {code} "
                    f"is offered to {course_cohort}"))

        students_with_registration.add(student_id)
        codes_with_registration.add(code)
        section_codes.add((section_id, code))

    for student_id in section_of:
        if student_id not in students_with_registration:
            file_name, row_number = first_seen[student_id]
            problems.append(Problem(
                file_name, row_number, "student has a registration",
                f"student {student_id} has no registrations"))
    for code, row in courses.items():
        if code not in codes_with_registration:
            problems.append(Problem(
                "courses.csv", row["_row"], "course code has a registration",
                f"nobody is registered for {code}, so it has no exam"))
    return section_codes


def check_teaching(data, teachers, courses, sections, section_codes, problems):
    for row in data["teaching"]:
        teacher_id = row["teacher_id"]
        code = row["course_code"]
        section_id = row["section_id"]
        if teacher_id not in teachers:
            problems.append(Problem(
                "teaching.csv", row["_row"], "teacher exists",
                f"teacher {teacher_id or '(blank)'} is not in teachers.csv"))
        if code not in courses:
            problems.append(Problem(
                "teaching.csv", row["_row"], "course code exists",
                f"course code {code or '(blank)'} is not in courses.csv"))
        if section_id not in sections:
            problems.append(Problem(
                "teaching.csv", row["_row"], "section exists",
                f"section {section_id or '(blank)'} is not in sections.csv"))
        if code not in courses or section_id not in sections:
            continue

        course_cohort = courses[code]["cohort_id"]
        section_cohort = sections[section_id]["cohort_id"]
        if course_cohort != section_cohort:
            problems.append(Problem(
                "teaching.csv", row["_row"],
                "course is offered to the section's cohort",
                f"{code} is offered to {course_cohort}, but {section_id} "
                f"is in {section_cohort}"))
        elif (section_id, code) not in section_codes:
            problems.append(Problem(
                "teaching.csv", row["_row"],
                "section has students writing the course",
                f"no student of {section_id} is registered for {code}"))


def as_date(value):
    """A YAML date (2026-11-02) or a 'YYYY-MM-DD' string -> date, else None."""
    if isinstance(value, datetime.datetime):
        return None  # a date with a time is not what settings.yaml wants
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def is_whole_number_at_least_1(value):
    # bool is excluded on purpose: in Python, True counts as the number 1.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def check_settings(settings, problems):
    def report(rule, message):
        problems.append(Problem("settings.yaml", None, rule, message))

    for key in SETTING_KEYS:
        if key not in settings:
            report("setting is present", f"{key} is missing")

    dates = {}
    for key in ["start_date", "end_date"]:
        if key in settings:
            dates[key] = as_date(settings[key])
            if dates[key] is None:
                report("dates are valid",
                       f"{key} should be a date like 2026-11-02, "
                       f"found {settings[key]!r}")
    if dates.get("start_date") and dates.get("end_date"):
        if dates["start_date"] > dates["end_date"]:
            report("start_date is on or before end_date",
                   f"start_date {dates['start_date']} is after "
                   f"end_date {dates['end_date']}")

    if "exam_weekdays" in settings:
        weekdays = settings["exam_weekdays"]
        if not isinstance(weekdays, list) or not weekdays:
            report("exam_weekdays are valid",
                   "exam_weekdays should be a list like [Mon, Tue]")
        else:
            for day in weekdays:
                if day not in WEEKDAYS:
                    report("exam_weekdays are valid",
                           f"{day!r} is not one of {', '.join(WEEKDAYS)}")

    if "holidays" in settings:
        holidays = settings["holidays"]
        if holidays is None:
            holidays = []  # `holidays:` with nothing after it means none
        if not isinstance(holidays, list):
            report("dates are valid",
                   "holidays should be a list of dates like [2026-11-11]")
        else:
            for day in holidays:
                if as_date(day) is None:
                    report("dates are valid",
                           f"holiday {day!r} is not a date like 2026-11-11")

    if "sessions" in settings:
        sessions = settings["sessions"]
        if (not isinstance(sessions, list) or len(sessions) != 2
                or len(set(map(str, sessions))) != 2):
            report("exactly two sessions",
                   f"sessions should be two different names, found {sessions!r}")

    for key in ["min_gap_days", "invigilators_per_room"]:
        if key in settings and not is_whole_number_at_least_1(settings[key]):
            report("whole number of at least 1",
                   f"{key} should be a whole number of at least 1, "
                   f"found {settings[key]!r}")


def check_constraints(constraints, courses, problems):
    def report(rule, message):
        problems.append(Problem("constraints.yaml", None, rule, message))

    groups = constraints.get("same_paper", [])
    if groups is None:
        groups = []  # `same_paper:` with nothing after it means no groups
    if not isinstance(groups, list):
        report("same_paper is a list of groups",
               "same_paper should be a list of groups like [MTH2001, MTH3011]")
        return

    group_of = {}
    for number, group in enumerate(groups, start=1):
        label = f"same_paper group {number}"
        if not isinstance(group, list):
            report("same_paper is a list of groups",
                   f"{label} should be a list like [MTH2001, MTH3011], "
                   f"found {group!r}")
            continue
        if len(group) < 2:
            report("group has at least two codes",
                   f"{label} {group} has {len(group)} code(s)")
        for code in group:
            code = str(code)
            if code not in courses:
                report("course code exists",
                       f"{label}: course code {code} is not in courses.csv")
            if code in group_of:
                where = ("again in the same group" if group_of[code] == number
                         else f"also in same_paper group {group_of[code]}")
                report("code is in at most one group",
                       f"{label}: {code} is {where}")
            else:
                group_of[code] = number


def check_data(data):
    """Stage 2. Returns a list of Problems; empty means the input is valid."""
    problems = []
    sections, section_of, first_seen = check_sections(data, problems)
    courses = check_courses(data, sections, problems)
    check_rooms(data, problems)
    teachers = check_teachers(data, problems)
    section_codes = check_registrations(data, sections, section_of,
                                        first_seen, courses, problems)
    check_teaching(data, teachers, courses, sections, section_codes, problems)
    check_settings(data["settings"], problems)
    check_constraints(data["constraints"], courses, problems)
    return problems

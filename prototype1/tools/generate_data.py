from __future__ import annotations

import csv
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Parameters kept together so the team can change the generated datasets
# without digging through the generator logic.
# ---------------------------------------------------------------------------
SEED = 20261018  # Reserved for later datasets that need deterministic randomness.

MAIN_SECTION_SIZE = 48
MAIN_SECTIONS_PER_COHORT = 2
MAIN_CORE_PAPERS_PER_COHORT = 4
MAIN_SHARED_ELECTIVES = 4

MAIN_TEACHER_RANKS = [
    "PROF",
    "PROF",
    "ASSOC",
    "ASSOC",
    "ASSOC",
    "ASST",
    "ASST",
    "ASST",
    "ASST",
    "ASST",
    "ASST",
    "ASST",
    "PHD",
    "PHD",
    "PHD",
    "PHD",
]

MAIN_COHORTS = [
    {
        "cohort_id": "AIML2",
        "program": "BTECH_AIML",
        "year": 2,
        "student_prefix": "AIML2S",
        "course_prefix": "AIM",
        "core_titles": [
            "Machine Learning Foundations",
            "Data Structures for AI",
            "Probability and Statistics",
            "Database Systems",
        ],
    },
    {
        "cohort_id": "ECE2",
        "program": "BTECH_ECE",
        "year": 2,
        "student_prefix": "ECE2S",
        "course_prefix": "ECE",
        "core_titles": [
            "Analog Circuits",
            "Digital Electronics",
            "Signals and Systems",
            "Network Theory",
        ],
    },
    {
        "cohort_id": "CYB2",
        "program": "BTECH_CYBER",
        "year": 2,
        "student_prefix": "CYB2S",
        "course_prefix": "CYB",
        "core_titles": [
            "Network Security",
            "Operating Systems",
            "Cryptography Foundations",
            "Secure Programming",
        ],
    },
]

SHARED_ELECTIVE_TITLES = [
    "Professional Communication",
    "Applied Mathematics",
    "Environmental Studies",
    "Engineering Economics",
]

MAIN_SETTINGS = {
    "start_date": "2026-11-02",
    "end_date": "2026-11-13",
    "exam_weekdays": ["Mon", "Wed", "Fri"],
    "holidays": ["2026-11-11"],
    "sessions": ["morning", "evening"],
    "min_gap_days": 2,
    "invigilators_per_room": 2,
}

TINY_SETTINGS = {
    "start_date": "2026-11-02",
    "end_date": "2026-11-06",
    "exam_weekdays": ["Mon", "Wed", "Fri"],
    "holidays": [],
    "sessions": ["morning", "evening"],
    "min_gap_days": 2,
    "invigilators_per_room": 2,
}


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"


CSV_HEADERS = {
    "sections.csv": ["section_id", "cohort_id", "program", "year"],
    "courses.csv": ["course_code", "title", "cohort_id", "kind"],
    "registrations.csv": ["student_id", "course_code"],
    "rooms.csv": ["room_id", "type", "rows", "seat_columns"],
    "teachers.csv": ["teacher_id", "rank"],
    "teaching.csv": ["teacher_id", "course_code", "section_id"],
}


# ---------------------------------------------------------------------------
# Small file helpers
# ---------------------------------------------------------------------------
def reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False)


# ---------------------------------------------------------------------------
# Tiny dataset: deliberately small enough to inspect by hand.
# ---------------------------------------------------------------------------
def build_tiny() -> dict:
    sections = [
        ["AIML1_I", "AIML1", "BTECH_AIML", 1],
        ["CYB1_I", "CYB1", "BTECH_CYBER", 1],
    ]

    rosters = {
        "AIML1_I": [f"AIML1S{i:04d}" for i in range(1, 9)],
        "CYB1_I": [f"CYB1S{i:04d}" for i in range(1, 9)],
    }

    courses = [
        ["AIM1101", "Programming Fundamentals", "AIML1", "CORE"],
        ["AIM1102", "Discrete Mathematics", "AIML1", "CORE"],
        ["AIM1190", "Professional Communication", "AIML1", "ELECTIVE"],
        ["CYB1101", "Programming Fundamentals", "CYB1", "CORE"],
        ["CYB1102", "Computer Networks Basics", "CYB1", "CORE"],
        ["CYB1190", "Professional Communication", "CYB1", "ELECTIVE"],
    ]

    registrations: list[list[str]] = []
    for student_id in rosters["AIML1_I"]:
        registrations.extend(
            [[student_id, "AIM1101"], [student_id, "AIM1102"], [student_id, "AIM1190"]]
        )
    for student_id in rosters["CYB1_I"]:
        registrations.extend(
            [[student_id, "CYB1101"], [student_id, "CYB1102"], [student_id, "CYB1190"]]
        )

    rooms = [
        ["M01", "M", 7, 6],
        ["M02", "M", 7, 6],
        ["S01", "S", 6, 3],
    ]

    teachers = [
        ["T001", "PROF"],
        ["T002", "ASSOC"],
        ["T003", "ASST"],
        ["T004", "ASST"],
        ["T005", "ASST"],
        ["T006", "PHD"],
    ]

    # Keep teaching.csv empty in tiny. With only one section per cohort, any
    # course teacher would teach every student writing that cohort's core paper,
    # which hits the still-open duty edge case in model_spec §10. Main carries
    # the real teaching relationships instead.
    teaching: list[list[str]] = []

    constraints = {"same_paper": [["AIM1190", "CYB1190"]]}

    return {
        "settings": TINY_SETTINGS,
        "constraints": constraints,
        "sections": sections,
        "rosters": rosters,
        "courses": courses,
        "registrations": registrations,
        "rooms": rooms,
        "teachers": teachers,
        "teaching": teaching,
    }


# ---------------------------------------------------------------------------
# Main dataset B: regular enough to debug, but large enough to exercise rules.
# ---------------------------------------------------------------------------
def build_main() -> dict:
    sections: list[list[object]] = []
    rosters: dict[str, list[str]] = {}
    courses: list[list[str]] = []
    registrations: list[list[str]] = []
    teaching: list[list[str]] = []

    # Twelve non-PhD teachers are split as two teachers per section. Each teacher
    # teaches four papers to one section. This keeps the pool tight while avoiding
    # the open "teacher teaches every section writing a paper" case.
    non_phd_teachers = [f"T{i:03d}" for i in range(1, 13)]
    teacher_index = 0

    same_paper_groups: list[list[str]] = [[] for _ in range(MAIN_SHARED_ELECTIVES)]

    for cohort in MAIN_COHORTS:
        cohort_id = cohort["cohort_id"]
        program = cohort["program"]
        year = cohort["year"]
        student_prefix = cohort["student_prefix"]
        course_prefix = cohort["course_prefix"]

        section_ids = [f"{cohort_id}_I", f"{cohort_id}_II"]
        for section_number, section_id in enumerate(section_ids):
            sections.append([section_id, cohort_id, program, year])
            start = section_number * MAIN_SECTION_SIZE + 1
            stop = start + MAIN_SECTION_SIZE
            rosters[section_id] = [f"{student_prefix}{i:04d}" for i in range(start, stop)]

        core_codes: list[str] = []
        for offset, title in enumerate(cohort["core_titles"], start=1):
            code = f"{course_prefix}22{offset:02d}"
            core_codes.append(code)
            courses.append([code, title, cohort_id, "CORE"])

        elective_codes: list[str] = []
        for offset, title in enumerate(SHARED_ELECTIVE_TITLES, start=1):
            code = f"{course_prefix}21{offset:02d}"
            elective_codes.append(code)
            courses.append([code, title, cohort_id, "ELECTIVE"])
            same_paper_groups[offset - 1].append(code)

        # Two teachers per section. The first handles papers 1-2 and electives
        # 1-2; the second handles papers 3-4 and electives 3-4. For any paper,
        # section I and section II therefore have different teachers.
        for section_id in section_ids:
            teacher_a = non_phd_teachers[teacher_index]
            teacher_b = non_phd_teachers[teacher_index + 1]
            teacher_index += 2
            for code in core_codes[:2] + elective_codes[:2]:
                teaching.append([teacher_a, code, section_id])
            for code in core_codes[2:] + elective_codes[2:]:
                teaching.append([teacher_b, code, section_id])

        # Every student takes all four core papers.
        cohort_students = rosters[section_ids[0]] + rosters[section_ids[1]]
        for student_id in cohort_students:
            for code in core_codes:
                registrations.append([student_id, code])

        # Each section has 48 students. Split it into four ordered groups of 12,
        # one group per elective. Across two sections this gives 24 students per
        # elective in each cohort, hence 72 students per shared paper overall.
        for section_id in section_ids:
            section_students = rosters[section_id]
            for index, student_id in enumerate(section_students):
                elective_index = index // 12
                registrations.append([student_id, elective_codes[elective_index]])

    rooms = [[f"M{i:02d}", "M", 7, 6] for i in range(1, 6)]
    rooms.append(["S01", "S", 6, 3])

    teachers = [[f"T{i:03d}", rank] for i, rank in enumerate(MAIN_TEACHER_RANKS, start=1)]

    constraints = {"same_paper": same_paper_groups}

    return {
        "settings": MAIN_SETTINGS,
        "constraints": constraints,
        "sections": sections,
        "rosters": rosters,
        "courses": courses,
        "registrations": registrations,
        "rooms": rooms,
        "teachers": teachers,
        "teaching": teaching,
    }


# ---------------------------------------------------------------------------
# Writer and generated-data checks
# ---------------------------------------------------------------------------
def write_dataset(name: str, dataset: dict) -> Path:
    target = DATA_ROOT / name
    reset_directory(target)

    write_yaml(target / "settings.yaml", dataset["settings"])
    write_yaml(target / "constraints.yaml", dataset["constraints"])
    write_csv(target / "sections.csv", CSV_HEADERS["sections.csv"], dataset["sections"])
    write_csv(target / "courses.csv", CSV_HEADERS["courses.csv"], dataset["courses"])
    write_csv(
        target / "registrations.csv",
        CSV_HEADERS["registrations.csv"],
        dataset["registrations"],
    )
    write_csv(target / "rooms.csv", CSV_HEADERS["rooms.csv"], dataset["rooms"])
    write_csv(target / "teachers.csv", CSV_HEADERS["teachers.csv"], dataset["teachers"])
    write_csv(target / "teaching.csv", CSV_HEADERS["teaching.csv"], dataset["teaching"])

    sections_dir = target / "sections"
    sections_dir.mkdir()
    for section_id, students in dataset["rosters"].items():
        write_csv(sections_dir / f"{section_id}.csv", ["student_id"], [[s] for s in students])

    validate_written_dataset(target)
    return target


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames or [], list(reader)


def validate_written_dataset(path: Path) -> None:
    required = [
        "settings.yaml",
        "constraints.yaml",
        "sections.csv",
        "courses.csv",
        "registrations.csv",
        "rooms.csv",
        "teachers.csv",
        "teaching.csv",
    ]
    for filename in required:
        if not (path / filename).exists():
            raise ValueError(f"{path.name}: missing {filename}")

    tables: dict[str, list[dict[str, str]]] = {}
    for filename, expected_header in CSV_HEADERS.items():
        header, rows = read_csv(path / filename)
        if header != expected_header:
            raise ValueError(f"{path.name}/{filename}: header is {header}, expected {expected_header}")
        tables[filename] = rows

    sections = tables["sections.csv"]
    courses = tables["courses.csv"]
    registrations = tables["registrations.csv"]
    rooms = tables["rooms.csv"]
    teachers = tables["teachers.csv"]
    teaching = tables["teaching.csv"]

    section_ids = [row["section_id"] for row in sections]
    if len(section_ids) != len(set(section_ids)):
        raise ValueError(f"{path.name}: duplicate section_id")

    cohort_by_section = {row["section_id"]: row["cohort_id"] for row in sections}

    student_to_section: dict[str, str] = {}
    for section_id in section_ids:
        roster_path = path / "sections" / f"{section_id}.csv"
        header, roster = read_csv(roster_path)
        if header != ["student_id"]:
            raise ValueError(f"{path.name}/{roster_path.name}: wrong header")
        for row in roster:
            student_id = row["student_id"]
            if not student_id:
                raise ValueError(f"{path.name}/{roster_path.name}: blank student_id")
            if student_id in student_to_section:
                raise ValueError(f"{path.name}: student {student_id} appears in more than one section")
            student_to_section[student_id] = section_id

    course_codes = [row["course_code"] for row in courses]
    if len(course_codes) != len(set(course_codes)):
        raise ValueError(f"{path.name}: duplicate course_code")
    cohort_by_course = {row["course_code"]: row["cohort_id"] for row in courses}

    seen_registrations: set[tuple[str, str]] = set()
    registration_count = Counter()
    registered_by_course_section: dict[tuple[str, str], int] = defaultdict(int)
    for row in registrations:
        student_id = row["student_id"]
        course_code = row["course_code"]
        pair = (student_id, course_code)
        if pair in seen_registrations:
            raise ValueError(f"{path.name}: duplicate registration {pair}")
        seen_registrations.add(pair)
        if student_id not in student_to_section:
            raise ValueError(f"{path.name}: unknown student {student_id} in registrations.csv")
        if course_code not in cohort_by_course:
            raise ValueError(f"{path.name}: unknown course {course_code} in registrations.csv")
        section_id = student_to_section[student_id]
        if cohort_by_section[section_id] != cohort_by_course[course_code]:
            raise ValueError(f"{path.name}: {student_id} registered outside their cohort")
        registration_count[student_id] += 1
        registered_by_course_section[(course_code, section_id)] += 1

    if set(registration_count) != set(student_to_section):
        raise ValueError(f"{path.name}: every student must have at least one registration")
    if set(course_codes) - {row["course_code"] for row in registrations}:
        raise ValueError(f"{path.name}: every course must have at least one registration")

    for row in rooms:
        if row["type"] not in {"S", "M"}:
            raise ValueError(f"{path.name}: invalid room type {row['type']}")
        if int(row["rows"]) <= 0 or int(row["seat_columns"]) <= 0:
            raise ValueError(f"{path.name}: room dimensions must be positive")

    teacher_ids = [row["teacher_id"] for row in teachers]
    if len(teacher_ids) != len(set(teacher_ids)):
        raise ValueError(f"{path.name}: duplicate teacher_id")
    teacher_ranks = {row["teacher_id"]: row["rank"] for row in teachers}
    if any(rank not in {"PROF", "ASSOC", "ASST", "PHD"} for rank in teacher_ranks.values()):
        raise ValueError(f"{path.name}: invalid teacher rank")

    for row in teaching:
        teacher_id = row["teacher_id"]
        course_code = row["course_code"]
        section_id = row["section_id"]
        if teacher_id not in teacher_ranks:
            raise ValueError(f"{path.name}: unknown teacher {teacher_id} in teaching.csv")
        if teacher_ranks[teacher_id] == "PHD":
            raise ValueError(f"{path.name}: PhD scholars should not teach in this dataset")
        if course_code not in cohort_by_course or section_id not in cohort_by_section:
            raise ValueError(f"{path.name}: unknown course or section in teaching.csv")
        if cohort_by_course[course_code] != cohort_by_section[section_id]:
            raise ValueError(f"{path.name}: teaching row crosses cohorts")
        if registered_by_course_section[(course_code, section_id)] == 0:
            raise ValueError(
                f"{path.name}: no student in {section_id} is registered for {course_code}"
            )

    with (path / "settings.yaml").open(encoding="utf-8") as file:
        settings = yaml.safe_load(file)
    if settings["sessions"] != ["morning", "evening"]:
        raise ValueError(f"{path.name}: exactly morning/evening sessions are required")
    if int(settings["min_gap_days"]) < 1 or int(settings["invigilators_per_room"]) < 1:
        raise ValueError(f"{path.name}: invalid numeric setting")

    with (path / "constraints.yaml").open(encoding="utf-8") as file:
        constraints = yaml.safe_load(file) or {}
    used_codes: set[str] = set()
    for group in constraints.get("same_paper", []):
        if len(group) < 2:
            raise ValueError(f"{path.name}: same_paper group needs at least two codes")
        for code in group:
            if code not in cohort_by_course:
                raise ValueError(f"{path.name}: unknown same_paper code {code}")
            if code in used_codes:
                raise ValueError(f"{path.name}: {code} appears in more than one same_paper group")
            used_codes.add(code)


def print_summary(path: Path) -> None:
    _, sections = read_csv(path / "sections.csv")
    _, courses = read_csv(path / "courses.csv")
    _, registrations = read_csv(path / "registrations.csv")
    _, rooms = read_csv(path / "rooms.csv")
    _, teachers = read_csv(path / "teachers.csv")

    students = 0
    for row in sections:
        _, roster = read_csv(path / "sections" / f"{row['section_id']}.csv")
        students += len(roster)

    print(
        f"{path.name}: {students} students, {len(sections)} sections, "
        f"{len(courses)} course codes, {len(registrations)} registrations, "
        f"{len(rooms)} rooms, {len(teachers)} invigilators"
    )


def main() -> None:
    DATA_ROOT.mkdir(exist_ok=True)

    tiny_path = write_dataset("tiny", build_tiny())
    main_path = write_dataset("main", build_main())

    print_summary(tiny_path)
    print_summary(main_path)
    print("Generated datasets passed the generator's internal checks.")


if __name__ == "__main__":
    main()

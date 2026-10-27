"""Generate prototype1's input folders: data/tiny and data/main.

Run from prototype1/:

    python tools/generate_data.py

Every number comes from docs/data_design_spec.md section 8. All the numbers
sit in TINY and MAIN below, so they can be changed and the script re-run.
The same SEED always gives the same files.

How it works, in order:
  1. make sections and students (50 per section, IDs like BT2CSE0001)
  2. give every student their cohort's cores, and hand out electives randomly
     so each elective gets exactly the number of students in the spec
  3. give every (cohort, subject) its own course code; a subject written by
     several cohorts is one paper, so its codes go in constraints.yaml
  4. split each paper's sections into teaching groups and give each group
     a teacher
  5. write the CSV and YAML files, then read them back and run the checks
     from data_design_spec.md section 3
"""

import csv
import datetime
import math
import random
import shutil
import sys
from pathlib import Path

import yaml

SEED = 2026

# Room shapes (model spec section 9): type -> (rows, seat columns)
ROOM_SHAPES = {"S": (6, 3), "M": (7, 6)}

TEACHER_RANKS = ["PROF", "ASSOC", "ASST", "PHD"]

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

# Subject key -> (title, department). The department becomes the course
# code prefix. The same key in two cohorts means the same question paper.
# Discrete Maths has two keys because BT2 and BT3 write different papers.
SUBJECTS = {
    # BTech 2nd year
    "lade": ("Linear Algebra & Differential Equations", "MTH"),
    "dap": ("Data Analysis using Python", "CSE"),
    "dsa": ("Data Structures & Algorithms", "CSE"),
    "web": ("Web Programming", "CSE"),
    "dld": ("Digital Logic Design", "ECE"),
    "oops": ("OOPS using Java", "CSE"),
    "ie": ("Innovation & Entrepreneurship", "MGT"),
    "sigsys": ("Signals & Systems", "ECE"),
    "sensors_iot": ("Sensors & IoT", "ECE"),
    "robotics_iot": ("Robotics & IoT", "MEC"),
    "thermo": ("Thermodynamics", "MEC"),
    "eng_materials": ("Engineering Materials", "MEC"),
    "dm_bt2": ("Discrete Mathematics", "MTH"),
    "semi_phy": ("Semiconductor Physics", "PHY"),
    "quantum": ("Quantum", "PHY"),
    "modeling_life": ("Modeling Life", "BIO"),
    # BTech 3rd year
    "ml": ("Machine Learning", "CSE"),
    "coa": ("Computer Organization & Architecture", "CSE"),
    "ai": ("Artificial Intelligence", "CSE"),
    "iot": ("IoT", "ECE"),
    "coding_skills": ("Coding Skills", "CSE"),
    "dm_bt3": ("Discrete Mathematics", "MTH"),
    "mpmc": ("Microprocessors & Microcontrollers", "ECE"),
    "vlsi": ("Digital VLSI", "ECE"),
    "ads": ("Advanced Data Science", "CSE"),
    "big_data": ("Big Data", "CSE"),
    "cedha": ("CE&DHA", "CSE"),
    "sad": ("Security Attack & Defence", "CSE"),
    "applied_db": ("Applied Databases", "CSE"),
    # BTech 4th year
    "compiler": ("Compiler Design", "CSE"),
    "plc": ("Automation with PLC", "MEC"),
    "adv_mfg": ("Advanced Manufacturing", "MEC"),
    "agentic_ai": ("Agentic AI", "CSE"),
    "nlp": ("NLP", "CSE"),
    "idt": ("IDT", "CSE"),
    "cyber_forensics": ("Cyber Forensics", "CSE"),
    "sds": ("SDS", "CSE"),
    "cad_vlsi": ("CAD for VLSI", "ECE"),
    "sdm": ("Semiconductor Device Modeling", "ECE"),
    "ev": ("EV Technologies", "MEC"),
    "vehicle_dyn": ("Vehicle Dynamics", "MEC"),
    "cfd": ("CFD", "MEC"),
    "composites": ("Composite Materials", "MEC"),
    # BBA (names from the Phase 0 data)
    "macroecon": ("Macroeconomics", "MGT"),
    "bus_stat": ("Business Statistics", "MGT"),
    "bus_comm": ("Business Communication", "MGT"),
    "finance": ("Finance", "MGT"),
    "marketing": ("Marketing", "MGT"),
    "design_thinking": ("Design Thinking", "HUM"),
    "bus_law": ("Business Law", "LAW"),
    "strat_mgmt": ("Strategic Management", "MGT"),
    "ops_mgmt": ("Operations Management", "MGT"),
    "happiness": ("Happiness", "HUM"),
    "bim": ("Bringing Ideas to Market", "MGT"),
    "ethics": ("Ethics and Integrity in Business", "LAW"),
    "org_beh": ("Organizational Behaviour", "HUM"),
}


def cohort(cohort_id, program, year, sections, cores, electives=None,
           electives_per_student=0):
    """One cohort's design. electives maps subject key -> number of students."""
    return {
        "id": cohort_id,
        "program": program,
        "year": year,
        "sections": sections,
        "cores": cores,
        "electives": electives or {},
        "electives_per_student": electives_per_student,
    }


BT2_COMMON = ["lade", "dap", "ie"]

MAIN = {
    "name": "main",
    "section_size": 50,
    "cohorts": [
        cohort("BT2CSE", "BTECH", 2, 7,
               BT2_COMMON + ["dsa", "web", "dld", "oops"],
               {"dm_bt2": 150, "semi_phy": 90, "quantum": 70, "modeling_life": 40}, 1),
        cohort("BT2ECOM", "BTECH", 2, 1,
               BT2_COMMON + ["dsa", "web", "dld", "sigsys", "sensors_iot"]),
        cohort("BT2ME", "BTECH", 2, 1,
               BT2_COMMON + ["robotics_iot", "thermo", "eng_materials", "sensors_iot"]),
        cohort("BT3CSE", "BTECH", 3, 7,
               ["ml", "coa", "ai", "iot", "coding_skills", "dm_bt3"],
               {"ads": 160, "big_data": 70, "cedha": 50, "sad": 40, "applied_db": 30}, 1),
        cohort("BT3ECOM", "BTECH", 3, 1,
               ["ml", "coa", "mpmc", "vlsi", "coding_skills"],
               {"ads": 50}, 1),
        cohort("BT4CSE", "BTECH", 4, 7, [],
               {"agentic_ai": 200, "nlp": 150, "idt": 120, "cyber_forensics": 90,
                "sad": 80, "sds": 60}, 2),
        cohort("BT4ECOM", "BTECH", 4, 1, ["compiler", "big_data"],
               {"agentic_ai": 30, "nlp": 25, "idt": 20, "cad_vlsi": 15, "sdm": 10}, 2),
        cohort("BT4ME", "BTECH", 4, 1, ["plc", "adv_mfg"],
               {"ev": 35, "vehicle_dyn": 25, "cfd": 25, "composites": 15}, 2),
        cohort("BB2", "BBA", 2, 3, ["macroecon", "bus_stat", "bus_comm"],
               {"finance": 55, "marketing": 55, "design_thinking": 40}, 1),
        cohort("BB3", "BBA", 3, 3, ["bus_law", "strat_mgmt", "ops_mgmt", "happiness"],
               {"bim": 50, "ethics": 50, "org_beh": 50}, 1),
    ],
    "rooms": {"S": 18, "M": 18},
    # 85 teachers: 10 PhD scholars; the other 75 split 20% / 30% / 50%
    "teachers": {"PROF": 15, "ASSOC": 22, "ASST": 38, "PHD": 10},
    # A core paper's sections are split into groups of at most this many
    # sections, with at least 2 groups when there are 2+ sections.
    "max_sections_per_core_group": 3,
    # An elective with this many students or more gets 2 teachers (2026-10-28).
    "big_elective_size": 150,
    "settings": {
        "start_date": datetime.date(2026, 11, 2),
        "end_date": datetime.date(2026, 11, 20),
        "exam_weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "holidays": [datetime.date(2026, 11, 11)],
        "sessions": ["morning", "evening"],
        "min_gap_days": 2,
        "invigilators_per_room": 2,
    },
}

TINY = {
    "name": "tiny",
    "section_size": 8,
    "cohorts": [
        cohort("BT2CSE", "BTECH", 2, 1, ["dsa", "oops"],
               {"dm_bt2": 5, "semi_phy": 3}, 1),
        cohort("BT2ECOM", "BTECH", 2, 1, ["dsa", "sigsys"],
               {"quantum": 5, "modeling_life": 3}, 1),
    ],
    "rooms": {"S": 2, "M": 1},
    "teachers": {"PROF": 2, "ASSOC": 2, "ASST": 4, "PHD": 1},
    "max_sections_per_core_group": 3,
    "big_elective_size": 150,
    "settings": {
        "start_date": datetime.date(2026, 11, 2),
        "end_date": datetime.date(2026, 11, 6),
        "exam_weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "holidays": [],
        "sessions": ["morning", "evening"],
        "min_gap_days": 2,
        "invigilators_per_room": 2,
    },
}

DATASETS = [TINY, MAIN]

# Exact headers from data_design_spec.md section 2
HEADERS = {
    "sections.csv": ["section_id", "cohort_id", "program", "year"],
    "courses.csv": ["course_code", "title", "cohort_id", "kind"],
    "registrations.csv": ["student_id", "course_code"],
    "rooms.csv": ["room_id", "type", "rows", "seat_columns"],
    "teachers.csv": ["teacher_id", "rank"],
    "teaching.csv": ["teacher_id", "course_code", "section_id"],
}


class DesignError(Exception):
    """The numbers in a dataset design don't add up."""


# ---------------------------------------------------------------- building

def make_sections_and_students(design):
    """Return (section rows, {section_id: [student_id, ...]}, {cohort_id: [student_id, ...]})."""
    section_rows = []
    students_by_section = {}
    students_by_cohort = {}
    for c in design["cohorts"]:
        if c["sections"] > len(ROMAN):
            raise DesignError(f"{c['id']}: more than {len(ROMAN)} sections")
        number = 1  # roll numbers run on across the cohort's sections
        students_by_cohort[c["id"]] = []
        for s in range(c["sections"]):
            section_id = f"{c['id']}_{ROMAN[s]}"
            section_rows.append([section_id, c["id"], c["program"], c["year"]])
            members = []
            for _ in range(design["section_size"]):
                members.append(f"{c['id']}{number:04d}")
                number += 1
            students_by_section[section_id] = members
            students_by_cohort[c["id"]].extend(members)
    return section_rows, students_by_section, students_by_cohort


def allocate_electives(cohort_id, students, electives, per_student, rng):
    """Give each student `per_student` different electives, with exact totals.

    The elective names are laid out in one long list, grouped by elective
    (e.g. 150 x dm_bt2, then 90 x semi_phy, ...). The students are shuffled,
    then list position i goes to student number (i mod number_of_students).

    With 2 electives each, a student gets positions i and i + n. Those are
    always different electives, because no elective has more than n students,
    so one elective's block is never long enough to cover both positions.
    """
    result = {student: [] for student in students}
    if per_student == 0:
        if electives:
            raise DesignError(f"{cohort_id}: has electives but 0 electives per student")
        return result

    n = len(students)
    total = sum(electives.values())
    if total != n * per_student:
        raise DesignError(
            f"{cohort_id}: elective sizes add up to {total}, "
            f"but {n} students x {per_student} = {n * per_student}")
    for name, count in electives.items():
        if count < 1 or count > n:
            raise DesignError(f"{cohort_id}: elective {name} has {count} students, "
                              f"must be between 1 and {n}")

    labels = []
    for name, count in electives.items():
        labels.extend([name] * count)

    order = list(students)
    rng.shuffle(order)
    for i, label in enumerate(labels):
        result[order[i % n]].append(label)
    return result


def make_course_codes(design):
    """Return {(cohort_id, subject): course_code}.

    Codes look like CSE2003: department, year digit, then a 3-digit counter
    per department and year. So a subject in two cohorts gets two codes.
    """
    counters = {}
    codes = {}
    for c in design["cohorts"]:
        for subject in c["cores"] + list(c["electives"]):
            if subject not in SUBJECTS:
                raise DesignError(f"{c['id']}: unknown subject {subject}")
            if (c["id"], subject) in codes:
                raise DesignError(f"{c['id']}: subject {subject} listed twice")
            dept = SUBJECTS[subject][1]
            key = (dept, c["year"])
            counters[key] = counters.get(key, 0) + 1
            codes[(c["id"], subject)] = f"{dept}{c['year']}{counters[key]:03d}"
    return codes


def split_evenly(items, parts):
    """Split a list into `parts` contiguous chunks, bigger chunks first.
    Example: 7 items into 3 parts -> sizes 3, 2, 2."""
    chunks = []
    start = 0
    for p in range(parts):
        size = len(items) // parts + (1 if p < len(items) % parts else 0)
        chunks.append(items[start:start + size])
        start += size
    return chunks


def make_teaching_groups(design, codes, registrations, students_by_section):
    """Split each paper's sections into groups; each group gets one teacher.

    A paper is one subject key, with all its cohorts' codes together.
    - Core paper with 1 section: 1 group.
    - Core paper with 2+ sections: groups of at most 3 sections, at least 2 groups.
    - Elective paper (any of its codes is an elective): 2 groups if it has
      150+ students in total, otherwise 1 group (2026-10-28 decision).
    Returns a list of (subject, [section_id, ...]).
    """
    kind_of = {}
    for c in design["cohorts"]:
        for subject in c["cores"]:
            kind_of[(c["id"], subject)] = "CORE"
        for subject in c["electives"]:
            kind_of[(c["id"], subject)] = "ELECTIVE"

    registered = set(registrations)  # (student_id, course_code)
    groups = []
    for subject in subjects_in_order(design):
        paper_codes = [(cid, code) for (cid, subj), code in codes.items() if subj == subject]
        is_core = all(kind_of[(cid, subject)] == "CORE" for cid, _ in paper_codes)

        sections = []
        students = 0
        for cid, code in paper_codes:
            for section_id, members in students_by_section.items():
                if not section_id.startswith(cid + "_"):
                    continue
                writers = sum(1 for s in members if (s, code) in registered)
                if writers:
                    sections.append(section_id)
                    students += writers

        if is_core:
            if len(sections) == 1:
                parts = 1
            else:
                parts = max(2, math.ceil(len(sections) / design["max_sections_per_core_group"]))
        else:
            parts = 2 if students >= design["big_elective_size"] else 1
        parts = min(parts, len(sections))

        for chunk in split_evenly(sections, parts):
            groups.append((subject, chunk))
    return groups


def subjects_in_order(design):
    """Every subject used, in the order it first appears in the design."""
    seen = []
    for c in design["cohorts"]:
        for subject in c["cores"] + list(c["electives"]):
            if subject not in seen:
                seen.append(subject)
    return seen


def make_teachers(design):
    """Return [(teacher_id, rank), ...]: PROF first, then ASSOC, ASST, PHD."""
    teachers = []
    number = 1
    for rank in TEACHER_RANKS:
        for _ in range(design["teachers"].get(rank, 0)):
            teachers.append((f"T{number:03d}", rank))
            number += 1
    return teachers


def assign_teachers(groups, teachers, rng):
    """Give each teaching group one non-PhD teacher.

    Groups are taken in a shuffled order. Each goes to the teacher with the
    fewest groups so far who doesn't already teach that paper (so a split
    paper really has different teachers). Ties go to the earlier teacher in
    a shuffled list, which mixes the ranks.
    Returns [(teacher_id, subject, [section_id, ...]), ...].
    """
    faculty = [tid for tid, rank in teachers if rank != "PHD"]
    if not faculty:
        raise DesignError("no non-PhD teachers to teach")
    rng.shuffle(faculty)
    load = {tid: 0 for tid in faculty}
    papers_of = {tid: set() for tid in faculty}

    order = list(groups)
    rng.shuffle(order)
    assigned = []
    for subject, sections in order:
        candidates = [t for t in faculty if subject not in papers_of[t]]
        if not candidates:
            raise DesignError(f"not enough teachers for paper {subject}")
        teacher = min(candidates, key=lambda t: load[t])  # min keeps the first on ties
        load[teacher] += 1
        papers_of[teacher].add(subject)
        assigned.append((teacher, subject, sections))
    return assigned


# ---------------------------------------------------------------- writing

def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)


def build_dataset(design, out_dir):
    rng = random.Random(SEED)

    section_rows, students_by_section, students_by_cohort = make_sections_and_students(design)
    codes = make_course_codes(design)

    # Registrations: all cores, plus the allocated electives
    registrations = []
    for c in design["cohorts"]:
        chosen = allocate_electives(c["id"], students_by_cohort[c["id"]], c["electives"],
                                    c["electives_per_student"], rng)
        for student in students_by_cohort[c["id"]]:
            for subject in c["cores"] + chosen[student]:
                registrations.append((student, codes[(c["id"], subject)]))

    groups = make_teaching_groups(design, codes, registrations, students_by_section)
    teachers = make_teachers(design)
    assigned = assign_teachers(groups, teachers, rng)

    registered = set(registrations)
    teaching_rows = []
    for teacher, subject, sections in assigned:
        for section_id in sections:
            cohort_id = section_id.rsplit("_", 1)[0]
            code = codes[(cohort_id, subject)]
            # only rows where this section really has students writing the code
            if any((s, code) in registered for s in students_by_section[section_id]):
                teaching_rows.append([teacher, code, section_id])
    teaching_rows.sort()

    # Write everything fresh
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "sections").mkdir(parents=True)

    write_csv(out_dir / "sections.csv", HEADERS["sections.csv"], section_rows)
    for section_id, members in students_by_section.items():
        write_csv(out_dir / "sections" / f"{section_id}.csv", ["student_id"],
                  [[s] for s in members])

    course_rows = []
    for c in design["cohorts"]:
        for subject in c["cores"]:
            course_rows.append([codes[(c["id"], subject)], SUBJECTS[subject][0], c["id"], "CORE"])
        for subject in c["electives"]:
            course_rows.append([codes[(c["id"], subject)], SUBJECTS[subject][0], c["id"], "ELECTIVE"])
    write_csv(out_dir / "courses.csv", HEADERS["courses.csv"], course_rows)

    write_csv(out_dir / "registrations.csv", HEADERS["registrations.csv"], registrations)

    room_rows = []
    for room_type in ["S", "M"]:
        rows, cols = ROOM_SHAPES[room_type]
        for i in range(1, design["rooms"].get(room_type, 0) + 1):
            room_rows.append([f"{room_type}{i:02d}", room_type, rows, cols])
    write_csv(out_dir / "rooms.csv", HEADERS["rooms.csv"], room_rows)

    write_csv(out_dir / "teachers.csv", HEADERS["teachers.csv"], teachers)
    write_csv(out_dir / "teaching.csv", HEADERS["teaching.csv"], teaching_rows)

    with open(out_dir / "settings.yaml", "w") as f:
        yaml.safe_dump(design["settings"], f, sort_keys=False, default_flow_style=None)

    same_paper = []
    for subject in subjects_in_order(design):
        group = [code for (cid, subj), code in codes.items() if subj == subject]
        if len(group) >= 2:
            same_paper.append(group)
    with open(out_dir / "constraints.yaml", "w") as f:
        yaml.safe_dump({"same_paper": same_paper}, f, sort_keys=False, default_flow_style=None)

    return codes, registrations, assigned, teachers


# ---------------------------------------------------------------- checks

def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def check_folder(folder):
    """Re-read a written input folder and check data_design_spec.md section 3.
    Returns a list of problems; an empty list means everything is fine."""
    problems = []
    tables = {}

    for name, header in HEADERS.items():
        path = folder / name
        if not path.exists():
            problems.append(f"{name}: file missing")
            continue
        rows = read_csv(path)
        if not rows or rows[0] != header:
            problems.append(f"{name}: header should be {','.join(header)}")
            continue
        tables[name] = rows[1:]
    for name in ["settings.yaml", "constraints.yaml"]:
        if not (folder / name).exists():
            problems.append(f"{name}: file missing")
    if problems:
        return problems  # can't check further without the files

    def unique_ids(name):
        ids = {}
        for i, row in enumerate(tables[name], start=2):
            if not row or not row[0].strip():
                problems.append(f"{name} row {i}: blank ID")
            elif row[0] in ids:
                problems.append(f"{name} row {i}: duplicate ID {row[0]}")
            else:
                ids[row[0]] = row
        return ids

    sections = unique_ids("sections.csv")
    courses = unique_ids("courses.csv")
    rooms = unique_ids("rooms.csv")
    teachers = unique_ids("teachers.csv")

    # Students: exactly one section each
    section_of = {}
    for section_id in sections:
        path = folder / "sections" / f"{section_id}.csv"
        if not path.exists():
            problems.append(f"sections/{section_id}.csv: file missing")
            continue
        rows = read_csv(path)
        if not rows or rows[0] != ["student_id"]:
            problems.append(f"sections/{section_id}.csv: header should be student_id")
            continue
        for i, row in enumerate(rows[1:], start=2):
            if not row or not row[0].strip():
                problems.append(f"sections/{section_id}.csv row {i}: blank student ID")
            elif row[0] in section_of:
                problems.append(f"sections/{section_id}.csv row {i}: student {row[0]} "
                                f"is also in {section_of[row[0]]}")
            else:
                section_of[row[0]] = section_id
    for path in (folder / "sections").glob("*.csv"):
        if path.stem not in sections:
            problems.append(f"sections/{path.name}: section not in sections.csv")

    # Registrations
    seen = set()
    students_with_reg = set()
    codes_with_reg = set()
    for i, row in enumerate(tables["registrations.csv"], start=2):
        if len(row) != 2:
            problems.append(f"registrations.csv row {i}: needs 2 columns")
            continue
        student, code = row
        if student not in section_of:
            problems.append(f"registrations.csv row {i}: student {student} is in no section file")
            continue
        if code not in courses:
            problems.append(f"registrations.csv row {i}: course code {code} is not in courses.csv")
            continue
        if (student, code) in seen:
            problems.append(f"registrations.csv row {i}: duplicate row")
        seen.add((student, code))
        student_cohort = sections[section_of[student]][1]
        if courses[code][2] != student_cohort:
            problems.append(f"registrations.csv row {i}: {student} ({student_cohort}) "
                            f"registered for {code} of cohort {courses[code][2]}")
        students_with_reg.add(student)
        codes_with_reg.add(code)
    for student in section_of:
        if student not in students_with_reg:
            problems.append(f"student {student} has no registration")
    for code in courses:
        if code not in codes_with_reg:
            problems.append(f"courses.csv: course code {code} has no registration")

    # Rooms and teachers
    for i, row in enumerate(tables["rooms.csv"], start=2):
        if len(row) != 4 or row[1] not in ROOM_SHAPES:
            problems.append(f"rooms.csv row {i}: type must be S or M")
            continue
        if not (row[2].isdigit() and int(row[2]) > 0 and row[3].isdigit() and int(row[3]) > 0):
            problems.append(f"rooms.csv row {i}: rows and seat_columns must be positive whole numbers")
    for i, row in enumerate(tables["teachers.csv"], start=2):
        if len(row) != 2 or row[1] not in TEACHER_RANKS:
            problems.append(f"teachers.csv row {i}: rank must be one of {', '.join(TEACHER_RANKS)}")

    # Teaching
    for i, row in enumerate(tables["teaching.csv"], start=2):
        if len(row) != 3:
            problems.append(f"teaching.csv row {i}: needs 3 columns")
            continue
        teacher, code, section_id = row
        if teacher not in teachers:
            problems.append(f"teaching.csv row {i}: teacher {teacher} is not in teachers.csv")
        if code not in courses:
            problems.append(f"teaching.csv row {i}: course code {code} is not in courses.csv")
            continue
        if section_id not in sections:
            problems.append(f"teaching.csv row {i}: section {section_id} is not in sections.csv")
            continue
        if courses[code][2] != sections[section_id][1]:
            problems.append(f"teaching.csv row {i}: {code} is not offered to {section_id}'s cohort")
        if not any((s, code) in seen for s, sec in section_of.items() if sec == section_id):
            problems.append(f"teaching.csv row {i}: no student of {section_id} writes {code}")

    # settings.yaml
    with open(folder / "settings.yaml") as f:
        settings = yaml.safe_load(f) or {}
    start, end = settings.get("start_date"), settings.get("end_date")
    if not isinstance(start, datetime.date) or not isinstance(end, datetime.date):
        problems.append("settings.yaml: start_date and end_date must be valid dates")
    elif start > end:
        problems.append("settings.yaml: start_date is after end_date")
    for day in settings.get("holidays") or []:
        if not isinstance(day, datetime.date):
            problems.append(f"settings.yaml: holiday {day} is not a valid date")
    if len(settings.get("sessions") or []) != 2:
        problems.append("settings.yaml: there must be exactly two sessions")
    for key in ["min_gap_days", "invigilators_per_room"]:
        value = settings.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            problems.append(f"settings.yaml: {key} must be a whole number of at least 1")

    # constraints.yaml
    with open(folder / "constraints.yaml") as f:
        constraints = yaml.safe_load(f) or {}
    group_of = {}
    for g, group in enumerate(constraints.get("same_paper") or [], start=1):
        if not isinstance(group, list) or len(group) < 2:
            problems.append(f"constraints.yaml same_paper group {g}: needs at least two codes")
            continue
        for code in group:
            if code not in courses:
                problems.append(f"constraints.yaml same_paper group {g}: {code} is not in courses.csv")
            elif code in group_of:
                problems.append(f"constraints.yaml: {code} is in groups {group_of[code]} and {g}")
            else:
                group_of[code] = g

    return problems


# ---------------------------------------------------------------- summary

def print_summary(design, codes, registrations, assigned, teachers):
    students_per_code = {}
    for _, code in registrations:
        students_per_code[code] = students_per_code.get(code, 0) + 1
    teachers_per_subject = {}
    for teacher, subject, _ in assigned:
        teachers_per_subject.setdefault(subject, []).append(teacher)

    total_students = sum(c["sections"] for c in design["cohorts"]) * design["section_size"]
    print(f"  {total_students} students, {len(codes)} course codes, "
          f"{len(subjects_in_order(design))} papers, {len(teachers)} teachers")
    print(f"  {'paper':<40} {'students':>8}  teachers  codes")
    for subject in subjects_in_order(design):
        paper_codes = [code for (cid, subj), code in codes.items() if subj == subject]
        students = sum(students_per_code.get(code, 0) for code in paper_codes)
        print(f"  {SUBJECTS[subject][0]:<40} {students:>8}  "
              f"{len(teachers_per_subject.get(subject, [])):>8}  {', '.join(paper_codes)}")

    load = {}
    for teacher, _, _ in assigned:
        load[teacher] = load.get(teacher, 0) + 1
    counts = {}
    for tid, rank in teachers:
        if rank != "PHD":
            counts[load.get(tid, 0)] = counts.get(load.get(tid, 0), 0) + 1
    spread = ", ".join(f"{n} teach {k} paper group(s)" for k, n in sorted(counts.items()))
    print(f"  teaching load (non-PhD): {spread}")


def main():
    prototype_dir = Path(__file__).resolve().parent.parent
    failed = False
    for design in DATASETS:
        out_dir = prototype_dir / "data" / design["name"]
        print(f"{design['name']}: writing {out_dir}")
        try:
            codes, registrations, assigned, teachers = build_dataset(design, out_dir)
        except DesignError as e:
            print(f"  design error: {e}")
            failed = True
            continue
        print_summary(design, codes, registrations, assigned, teachers)
        problems = check_folder(out_dir)
        if problems:
            failed = True
            print(f"  {len(problems)} problem(s):")
            for p in problems:
                print(f"    {p}")
        else:
            print("  checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

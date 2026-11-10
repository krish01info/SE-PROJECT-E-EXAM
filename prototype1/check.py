"""Step 8: the checker (model spec sections 13 and 14).

Reads an input folder and a plan folder written by main.py, and checks the
plan against every yes/no rule of the spec. It never writes a file.

Run from prototype1/:

    python check.py data/tiny output/<timestamp>

Decisions (Krish, 2026-11-05):

  - Only the yes/no rules are checked. The "try to" rules (one paper per room
    where possible, one shift a day, PhD scholars last, fewest duties first,
    biggest paper first, rooms in rooms.csv order, a new section in a new
    room) are preferences, not rules.
  - The checker reads every file with its own code and imports nothing from
    the tool (loader.py, schedule.py, seat.py, duties.py), so a bug there
    can't hide from it ("we want it error-proof").
  - For each mistake it shows only the main issue, so it is easy to fix,
    without follow-on errors. The checks run in three stages:

      Stage 1, files.  The plan's files are there, readable and the right
                       shape. If anything here is broken, the checker stops.
      Stage 2, rows.   Each date sheet row, seat and duty row makes sense on
                       its own (known paper, student registered for it, paper
                       written in that slot, ...). A bad seat or duty row is
                       reported once and left out of stage 3.
      Stage 3, rules.  The rules that need many rows together (gap, column
                       rule, everyone seated once, roll order, teachers per
                       room, ...). Each paper in a slot, each room and each
                       teacher in a slot is reported at most once: the first
                       rule it breaks is the main issue.

Exit codes (Krish, 2026-11-05):
    0  the plan is clean
    1  can't check: the input folder or the plan folder can't be read
    2  nothing to check: the folder holds only why.txt (no plan possible)
    3  the plan breaks a rule; every problem is printed under its rule
"""

import argparse
import csv
import datetime
import sys
from pathlib import Path

import yaml

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PHD = "PHD"
SCHEDULE_COLUMNS = ["date", "session", "paper_id", "course_codes", "students"]
DUTY_COLUMNS = ["date", "session", "room_id", "teacher_id"]
SEATING_FOLDER = "daywise_seating_plans"
# basis.txt (on what basis the plan was made) and terms.md (what the words
# mean), both 2026-11-10, are allowed in a plan folder but not checked, and
# a plan without them is fine.
PLAN_ITEMS = ["schedule.csv", "duties.csv", SEATING_FOLDER, "basis.txt",
              "terms.md"]

# Every rule the checker knows, in the order problems are printed.
RULES = [
    # stage 1: files
    "output files", "room shape", "room cell",
    # stage 2: rows on their own
    "date sheet", "same paper", "exam days", "registration",
    "paper in its slot", "known teacher", "duty in a used room",
    # stage 3: rules over many rows
    "gap", "two papers at most", "one paper per column", "column rule",
    "seated once", "roll order",
    "one duty per slot", "teachers per room", "own students",
    "own paper duty",
]
STAGE_1_RULES = {"output files", "room shape", "room cell"}


class CannotCheck(Exception):
    """The input folder or the plan folder can't be read (exit 1)."""


class Problems:
    """Problems found so far, by rule."""

    def __init__(self):
        self.by_rule = {rule: [] for rule in RULES}

    def add(self, rule, text):
        self.by_rule[rule].append(text)

    def count(self):
        return sum(len(texts) for texts in self.by_rule.values())

    def report(self):
        rules_broken = [rule for rule in RULES if self.by_rule[rule]]
        lines = [f"Plan check: {self.count()} problem(s), "
                 f"{len(rules_broken)} rule(s) broken."]
        for rule in rules_broken:
            lines.append("")
            lines.append(f"Rule: {rule} ({len(self.by_rule[rule])})")
            lines.extend(f"  {text}" for text in self.by_rule[rule])
        return "\n".join(lines)


# ============================================================ reading files

def read_csv_file(path, skip_blank_lines=True):
    """All lines of a CSV file as (line_number, values), values stripped.
    A byte-order mark (added by Excel) is ignored. Raises OSError,
    UnicodeDecodeError or csv.Error if the file can't be read."""
    lines = []
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        for values in reader:
            values = [value.strip() for value in values]
            if skip_blank_lines and not any(values):
                continue
            lines.append((reader.line_num, values))
    return lines


def read_input_table(path, columns):
    """An input CSV file as a list of row dicts. Raises CannotCheck if it is
    missing, unreadable or lacks one of `columns`."""
    if not path.is_file():
        raise CannotCheck(f"{path} is missing.")
    try:
        lines = read_csv_file(path)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise CannotCheck(f"{path} can't be read ({error}).")
    if not lines:
        raise CannotCheck(f"{path} is empty.")
    header = lines[0][1]
    missing = [column for column in columns if column not in header]
    if missing:
        raise CannotCheck(f"{path} has no column {', '.join(missing)}.")
    return [dict(zip(header, values)) for _, values in lines[1:]]


def read_input_yaml(path):
    """A YAML file as a dict. Raises CannotCheck if it can't be read."""
    if not path.is_file():
        raise CannotCheck(f"{path} is missing.")
    try:
        with open(path, encoding="utf-8-sig") as file:
            content = yaml.safe_load(file)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise CannotCheck(f"{path} can't be read ({error}).")
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise CannotCheck(f"{path} should hold keys and values.")
    return content


def to_date(value):
    """A YAML date, or a 'YYYY-MM-DD' text, as a datetime.date.
    Raises ValueError for anything else."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def load_input(input_dir):
    """Everything the checker needs from the input folder, as one dict.
    Raises CannotCheck if the folder can't be read."""
    folder = Path(input_dir)
    if not folder.is_dir():
        raise CannotCheck(f"the input folder {folder} doesn't exist.")

    settings = read_input_yaml(folder / "settings.yaml")
    constraints = read_input_yaml(folder / "constraints.yaml")
    try:
        start = to_date(settings["start_date"])
        end = to_date(settings["end_date"])
        weekdays = {str(day) for day in settings["exam_weekdays"]}
        holidays = {to_date(day) for day in (settings.get("holidays") or [])}
        sessions = [str(session) for session in settings["sessions"]]
        gap = int(settings["min_gap_days"])
        per_room = int(settings["invigilators_per_room"])
    except (KeyError, TypeError, ValueError) as error:
        raise CannotCheck(f"{folder / 'settings.yaml'} has a missing or "
                          f"wrong value ({error}).")

    # Papers: codes in one same_paper group are one paper, its ID the first
    # code (model spec section 7). Any other code is its own paper.
    paper_of_code = {}
    for group in constraints.get("same_paper") or []:
        codes = [str(code) for code in group]
        for code in codes:
            paper_of_code[code] = codes[0]
    codes_of_paper = {}
    for course in read_input_table(folder / "courses.csv", ["course_code"]):
        code = course["course_code"]
        paper_id = paper_of_code.setdefault(code, code)
        codes_of_paper.setdefault(paper_id, []).append(code)

    students_of_paper = {paper_id: set() for paper_id in codes_of_paper}
    for row in read_input_table(folder / "registrations.csv",
                                ["student_id", "course_code"]):
        paper_id = paper_of_code.setdefault(row["course_code"],
                                            row["course_code"])
        students_of_paper.setdefault(paper_id, set()).add(row["student_id"])
        codes_of_paper.setdefault(paper_id, [row["course_code"]])

    section_of = {}
    for path in sorted((folder / "sections").glob("*.csv")):
        for row in read_input_table(path, ["student_id"]):
            section_of[row["student_id"]] = path.stem

    rooms = {}                     # room_id -> (rows, seat_columns)
    room_order = []                # room IDs in rooms.csv order
    for row in read_input_table(folder / "rooms.csv",
                                ["room_id", "rows", "seat_columns"]):
        try:
            rooms[row["room_id"]] = (int(row["rows"]), int(row["seat_columns"]))
        except ValueError:
            raise CannotCheck(f"{folder / 'rooms.csv'}: room {row['room_id']} "
                              f"has a size that is not a number.")
        room_order.append(row["room_id"])

    rank_of = {row["teacher_id"]: row["rank"]
               for row in read_input_table(folder / "teachers.csv",
                                           ["teacher_id", "rank"])}

    teaches = {}                   # teacher_id -> {(paper_id, section_id)}
    for row in read_input_table(folder / "teaching.csv",
                                ["teacher_id", "course_code", "section_id"]):
        paper_id = paper_of_code.get(row["course_code"], row["course_code"])
        teaches.setdefault(row["teacher_id"], set()).add(
            (paper_id, row["section_id"]))

    return {
        "start": start, "end": end, "weekdays": weekdays,
        "holidays": holidays, "sessions": sessions, "gap": gap,
        "per_room": per_room, "codes_of_paper": codes_of_paper,
        "students_of_paper": students_of_paper, "section_of": section_of,
        "rooms": rooms, "room_order": room_order, "rank_of": rank_of,
        "teaches": teaches,
    }


# ================================================== stage 1: the plan files

def read_plan_table(folder, name, columns, sessions, problems):
    """schedule.csv or duties.csv as a list of row dicts, with "_row" (line
    number, header = row 1), "_day" and "_session". A row with a wrong date,
    session or number of values is reported and left out."""
    path = folder / name
    if not path.is_file():
        problems.add("output files", f"{name} is missing.")
        return []
    try:
        lines = read_csv_file(path)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        problems.add("output files", f"{name} can't be read ({error}).")
        return []
    if not lines or lines[0][1] != columns:
        problems.add("output files",
                     f"{name}: the header should be {','.join(columns)}.")
        return []

    rows = []
    for line, values in lines[1:]:
        where = f"{name} row {line}"
        if len(values) != len(columns):
            problems.add("output files", f"{where}: {len(values)} values, "
                                         f"should be {len(columns)}.")
            continue
        row = dict(zip(columns, values), _row=line)
        try:
            row["_day"] = datetime.date.fromisoformat(row["date"])
        except ValueError:
            problems.add("output files",
                         f"{where}: '{row['date']}' is not a date (YYYY-MM-DD).")
            continue
        if row["session"] not in sessions:
            problems.add("output files", f"{where}: '{row['session']}' is not "
                                         f"a session ({', '.join(sessions)}).")
            continue
        row["_session"] = row["session"]
        rows.append(row)
    return rows


def read_room_file(path, where, size, problems):
    """One room CSV as a grid: grid[row][column] = (paper_id, student_id) or
    None for an empty seat. Returns None (and reports) if the file has the
    wrong shape or a bad cell."""
    rows, columns = size
    try:
        lines = read_csv_file(path, skip_blank_lines=False)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        problems.add("output files", f"{where} can't be read ({error}).")
        return None
    if len(lines) != rows or any(len(values) != columns
                                 for _, values in lines):
        found = sorted({len(values) for _, values in lines})
        seats = " or ".join(str(number) for number in found) or "0"
        problems.add("room shape",
                     f"{where}: {len(lines)} rows of {seats} seats; this room "
                     f"has {rows} rows of {columns} seats.")
        return None

    grid = []
    good = True
    for row_number, (_, values) in enumerate(lines, start=1):
        grid_row = []
        for column_number, text in enumerate(values, start=1):
            if text == "":
                grid_row.append(None)
                continue
            parts = text.split(":")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                problems.add("room cell",
                             f"{where} row {row_number}, column "
                             f"{column_number}: '{text}' should be "
                             f"PAPER:STUDENT or empty.")
                good = False
                grid_row.append(None)
                continue
            grid_row.append((parts[0], parts[1]))
        grid.append(grid_row)
    if good and not any(cell for grid_row in grid for cell in grid_row):
        problems.add("output files", f"{where}: no student sits here; only "
                                     f"rooms in use get a file.")
        return None
    return grid if good else None


def read_seating(folder, data, problems):
    """Every room CSV, as a list of dicts with "where" (its path in the plan
    folder), "slot" (day, session), "room_id" and "grid"."""
    seating_folder = folder / SEATING_FOLDER
    if not seating_folder.is_dir():
        problems.add("output files", f"{SEATING_FOLDER}/ is missing.")
        return []

    room_files = []
    for day_folder in sorted(seating_folder.iterdir()):
        name = f"{SEATING_FOLDER}/{day_folder.name}"
        try:
            day = datetime.date.fromisoformat(day_folder.name)
        except ValueError:
            problems.add("output files", f"{name}: should be a folder named "
                                         f"by a date (YYYY-MM-DD).")
            continue
        if not day_folder.is_dir():
            problems.add("output files", f"{name}: should be a folder.")
            continue
        for session_folder in sorted(day_folder.iterdir()):
            name = f"{SEATING_FOLDER}/{day_folder.name}/{session_folder.name}"
            if (not session_folder.is_dir()
                    or session_folder.name not in data["sessions"]):
                problems.add("output files",
                             f"{name}: should be a session folder "
                             f"({', '.join(data['sessions'])}).")
                continue
            for path in sorted(session_folder.iterdir()):
                where = f"{name}/{path.name}"
                room_id = path.stem
                if path.suffix != ".csv" or room_id not in data["rooms"]:
                    problems.add("output files", f"{where}: not a room CSV "
                                                 f"of a room in rooms.csv.")
                    continue
                grid = read_room_file(path, where, data["rooms"][room_id],
                                      problems)
                if grid is not None:
                    room_files.append({"where": where,
                                       "slot": (day, session_folder.name),
                                       "room_id": room_id, "grid": grid})
    return room_files


def read_plan(folder, data, problems):
    """Stage 1. Returns (schedule rows, duty rows, room files)."""
    for item in sorted(folder.iterdir()):
        if item.name not in PLAN_ITEMS:
            problems.add("output files",
                         f"{item.name}: a plan folder holds only "
                         f"schedule.csv, duties.csv, basis.txt, terms.md and "
                         f"{SEATING_FOLDER}/.")
    schedule_rows = read_plan_table(folder, "schedule.csv", SCHEDULE_COLUMNS,
                                    data["sessions"], problems)
    duty_rows = read_plan_table(folder, "duties.csv", DUTY_COLUMNS,
                                data["sessions"], problems)
    room_files = read_seating(folder, data, problems)
    return schedule_rows, duty_rows, room_files


# ============================================== stage 2: rows on their own

def slot_text(slot):
    day, session = slot
    return f"{day} {session}"


def check_date_sheet(schedule_rows, data, problems):
    """Each paper has exactly one row (rule 1), with its own course codes
    (rule 4), on an exam day (rule 2). Returns ({paper_id: slot},
    {paper_id: schedule row}, papers left out of later checks)."""
    rows_of_paper = {}
    for row in schedule_rows:
        rows_of_paper.setdefault(row["paper_id"], []).append(row)

    slot_of = {}
    row_of = {}
    skipped = set()
    for paper_id, rows in sorted(rows_of_paper.items()):
        if paper_id not in data["codes_of_paper"]:
            for row in rows:
                problems.add("date sheet", f"schedule.csv row {row['_row']}: "
                                           f"{paper_id} is not a paper in "
                                           f"the input.")
            skipped.add(paper_id)
            continue
        if len(rows) > 1:
            numbers = ", ".join(str(row["_row"]) for row in rows)
            problems.add("date sheet", f"{paper_id} has {len(rows)} rows in "
                                       f"schedule.csv (rows {numbers}); a "
                                       f"paper is written in exactly one slot.")
            skipped.add(paper_id)
            continue
        row = rows[0]
        slot_of[paper_id] = (row["_day"], row["_session"])
        row_of[paper_id] = row
        where = f"schedule.csv row {row['_row']}"

        codes = sorted(code for code in row["course_codes"].split(";") if code)
        expected = sorted(data["codes_of_paper"][paper_id])
        if codes != expected:
            problems.add("same paper", f"{where}: {paper_id} lists "
                                       f"{';'.join(codes) or 'no codes'}, but "
                                       f"its course codes are "
                                       f"{';'.join(expected)}.")
        students = len(data["students_of_paper"][paper_id])
        if row["students"] != str(students):
            problems.add("date sheet", f"{where}: {paper_id} says "
                                       f"{row['students']} students; "
                                       f"{students} are registered.")

        day = row["_day"]
        weekday = WEEKDAY_NAMES[day.weekday()]
        reason = None
        if day < data["start"] or day > data["end"]:
            reason = f"outside {data['start']} to {data['end']}"
        elif weekday not in data["weekdays"]:
            reason = f"a {weekday}, not an exam weekday"
        elif day in data["holidays"]:
            reason = "a holiday"
        if reason:
            problems.add("exam days", f"{where}: {paper_id} is on {day}, "
                                      f"{reason}.")

    for paper_id in sorted(data["codes_of_paper"]):
        if paper_id not in rows_of_paper:
            problems.add("date sheet", f"{paper_id} is not in schedule.csv; "
                                       f"every paper gets one slot.")
            skipped.add(paper_id)
    return slot_of, row_of, skipped


def check_seats_alone(room_files, data, slot_of, row_of, skipped, problems):
    """Each seat on its own: the student exists and is registered for the
    paper, and the paper is written in that slot. Returns (good seats,
    students of bad seats, papers seated outside their slot, (paper_id,
    slot) pairs with a seat holding a wrong student). A seat is a dict:
    where, slot, room_id, row, column, paper_id, student_id."""
    good_seats = []
    bad_students = set()
    wrong_student = set()          # (paper_id, slot) with a wrong student
    wrong_slot = {}                # (paper_id, slot) -> [seat, ...]
    for room_file in room_files:
        for row_number, grid_row in enumerate(room_file["grid"], start=1):
            for column_number, cell in enumerate(grid_row, start=1):
                if cell is None:
                    continue
                paper_id, student_id = cell
                seat = {"where": f"{room_file['where']} row {row_number}, "
                                 f"column {column_number}",
                        "slot": room_file["slot"],
                        "room_id": room_file["room_id"],
                        "row": row_number, "column": column_number,
                        "paper_id": paper_id, "student_id": student_id}
                if paper_id in skipped:
                    bad_students.add(student_id)  # its date sheet row is wrong
                    continue
                if paper_id not in data["students_of_paper"]:
                    problems.add("registration", f"{seat['where']}: "
                                                 f"{paper_id} is not a paper "
                                                 f"in the input.")
                elif student_id not in data["section_of"]:
                    problems.add("registration", f"{seat['where']}: "
                                                 f"{student_id} is not a "
                                                 f"student in the input.")
                    wrong_student.add((paper_id, seat["slot"]))
                elif student_id not in data["students_of_paper"][paper_id]:
                    problems.add("registration", f"{seat['where']}: "
                                                 f"{student_id} sits for "
                                                 f"{paper_id}, but is not "
                                                 f"registered for it.")
                    wrong_student.add((paper_id, seat["slot"]))
                elif seat["slot"] != slot_of[paper_id]:
                    wrong_slot.setdefault((paper_id, seat["slot"]),
                                          []).append(seat)
                else:
                    good_seats.append(seat)
                    continue
                bad_students.add(student_id)

    for (paper_id, slot), seats in sorted(wrong_slot.items(),
                                          key=lambda item: (item[0][0],
                                                            item[0][1])):
        row = row_of[paper_id]
        planned = f"schedule.csv row {row['_row']} has it on " \
                  f"{slot_text(slot_of[paper_id])}"
        if len(seats) == 1:
            problems.add("paper in its slot", f"{seats[0]['where']}: "
                                              f"{paper_id} sits here on "
                                              f"{slot_text(slot)}, but "
                                              f"{planned}.")
        else:
            rooms = ", ".join(sorted({seat["room_id"] for seat in seats}))
            problems.add("paper in its slot", f"{paper_id} has {len(seats)} "
                                              f"seats on {slot_text(slot)} "
                                              f"({rooms}), but {planned}.")
    wrong_slot_papers = {paper_id for paper_id, _ in wrong_slot}
    return good_seats, bad_students, wrong_slot_papers, wrong_student


def check_duty_rows_alone(duty_rows, data, room_slots, problems):
    """Each duty row on its own: a known teacher, in a room that is in use
    in that slot (rule 23). Returns (good rows, rooms (slot, room_id) named
    in a bad row)."""
    good_rows = []
    rooms_of_bad_rows = set()
    for row in duty_rows:
        slot = (row["_day"], row["_session"])
        where = f"duties.csv row {row['_row']}"
        if row["teacher_id"] not in data["rank_of"]:
            problems.add("known teacher", f"{where}: {row['teacher_id']} is "
                                          f"not in teachers.csv.")
            rooms_of_bad_rows.add((slot, row["room_id"]))
        elif (slot, row["room_id"]) not in room_slots:
            problems.add("duty in a used room",
                         f"{where}: {row['teacher_id']} has a duty in "
                         f"{row['room_id']} on {slot_text(slot)}, but no "
                         f"student sits there then.")
        else:
            good_rows.append(row)
    return good_rows, rooms_of_bad_rows


# ================================================ stage 3: the main rules

def check_gap(data, slot_of, doubtful):
    """Rule 3: a student's papers are at least min_gap_days apart. One
    problem per pair of papers, not per student. Papers in `doubtful`
    (date sheet and room files disagree) are left out: their real date is
    not known. Returns the texts."""
    papers_of_student = {}
    for paper_id, students in data["students_of_paper"].items():
        if paper_id in slot_of and paper_id not in doubtful:
            for student_id in students:
                papers_of_student.setdefault(student_id, set()).add(paper_id)

    shared = {}                    # (paper_a, paper_b) -> [student_id, ...]
    for student_id, papers in papers_of_student.items():
        papers = sorted(papers)
        for index, paper_a in enumerate(papers):
            for paper_b in papers[index + 1:]:
                days = abs((slot_of[paper_a][0] - slot_of[paper_b][0]).days)
                if days < data["gap"]:
                    shared.setdefault((paper_a, paper_b),
                                      []).append(student_id)

    texts = []
    for (paper_a, paper_b), students in sorted(shared.items()):
        day_a, day_b = slot_of[paper_a][0], slot_of[paper_b][0]
        days = abs((day_a - day_b).days)
        texts.append(f"{paper_a} ({day_a}) and {paper_b} ({day_b}) are "
                     f"{days} day(s) apart and share {len(students)} "
                     f"student(s), e.g. {min(students)}; min_gap_days is "
                     f"{data['gap']}.")
    return texts


def check_rooms(room_files, good_seats, problems):
    """Rules 12, 13 and 8, per room: at most two papers, one paper per seat
    column, the column rule. Only the first rule a room breaks is reported.
    Returns the (slot, paper_id) pairs of rooms with a problem."""
    seats_of_room = {}
    for seat in good_seats:
        seats_of_room.setdefault((seat["slot"], seat["room_id"]),
                                 []).append(seat)

    reported = set()
    for room_file in room_files:
        key = (room_file["slot"], room_file["room_id"])
        seats = seats_of_room.get(key, [])
        papers = sorted({seat["paper_id"] for seat in seats})
        columns = len(room_file["grid"][0])
        papers_in_column = [set() for _ in range(columns)]
        for seat in seats:
            papers_in_column[seat["column"] - 1].add(seat["paper_id"])
        where = room_file["where"]

        if len(papers) > 2:
            problems.add("two papers at most",
                         f"{where}: {len(papers)} papers "
                         f"({', '.join(papers)}); a room holds at most two.")
        elif any(len(column) > 1 for column in papers_in_column):
            number = next(index for index, column
                          in enumerate(papers_in_column, start=1)
                          if len(column) > 1)
            problems.add("one paper per column",
                         f"{where}, column {number}: "
                         f"{', '.join(sorted(papers_in_column[number - 1]))} "
                         f"share one seat column.")
        else:
            side_by_side = [(index, paper_id)
                            for index in range(columns - 1)
                            for paper_id in sorted(papers_in_column[index]
                                                   & papers_in_column[index + 1])]
            if not side_by_side:
                continue
            index, paper_id = side_by_side[0]
            # Both columns' seats of that paper, so the stray seat is easy to
            # spot (Krish, 2026-11-05). Which side is wrong can't be known.
            lines = [f"{where}, columns {index + 1} and {index + 2}: "
                     f"{paper_id} sits in both, side by side."]
            for column in (index + 1, index + 2):
                seats_here = sorted((seat for seat in seats
                                     if seat["column"] == column
                                     and seat["paper_id"] == paper_id),
                                    key=lambda seat: seat["row"])
                rows_text = ", ".join(str(seat["row"]) for seat in seats_here)
                students = ", ".join(seat["student_id"] for seat in seats_here)
                word = "row" if len(seats_here) == 1 else "rows"
                lines.append(f"    column {column}: {word} {rows_text} "
                             f"({students})")
            problems.add("column rule", "\n".join(lines))
        for paper_id in papers:
            reported.add((room_file["slot"], paper_id))
    return reported


def check_seated_once(data, slot_of, good_seats, bad_students, wrong_student,
                      reported):
    """Rules 9 and 10: every registered student of a paper has exactly one
    seat in its slot. One problem per paper. Adds the papers it reports to
    `reported`. Returns the texts.

    If a seat of the paper also holds a wrong student (Rule: registration),
    both lines are kept and the reason is printed (Krish, 2026-11-05): the
    checker can't tell which missing student belonged in that seat, and
    guessing could hide a student who really has no seat."""
    seats_of_paper = {}
    for seat in good_seats:
        seats_of_paper.setdefault(seat["paper_id"], []).append(seat)

    texts = []
    for paper_id, slot in sorted(slot_of.items()):
        seats = seats_of_paper.get(paper_id, [])
        where_of = {}
        for seat in seats:
            where_of.setdefault(seat["student_id"], []).append(seat["where"])
        twice = sorted(student for student, places in where_of.items()
                       if len(places) > 1)
        missing = sorted(data["students_of_paper"][paper_id]
                         - set(where_of) - bad_students)
        if not twice and not missing:
            continue
        parts = [f"{student} has {len(where_of[student])} seats "
                 f"({'; '.join(where_of[student])})" for student in twice]
        if missing:
            shown = ", ".join(missing[:5])
            more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
            parts.append(f"no seat for {len(missing)} registered student(s): "
                         f"{shown}{more}")
        text = f"{paper_id} on {slot_text(slot)}: {'; '.join(parts)}."
        if missing and (paper_id, slot) in wrong_student:
            text += ("\n    Shown as well as Rule: registration: a seat of "
                     "this paper holds a wrong student, and the checker "
                     "can't tell which missing student belonged there. "
                     "Guessing could hide a student who really has no seat.")
        texts.append(text)
        reported.add((slot, paper_id))
    return texts


def check_roll_order(data, slot_of, good_seats, reported):
    """Rule 14: each paper's students sit in roll order (student_id), read
    front to back down each column, columns left to right, rooms in
    rooms.csv order. One problem per paper. Returns the texts."""
    room_index = {room_id: index
                  for index, room_id in enumerate(data["room_order"])}
    seats_of_paper = {}
    for seat in good_seats:
        seats_of_paper.setdefault(seat["paper_id"], []).append(seat)

    texts = []
    for paper_id, slot in sorted(slot_of.items()):
        if (slot, paper_id) in reported:
            continue
        seats = sorted(seats_of_paper.get(paper_id, []),
                       key=lambda seat: (room_index[seat["room_id"]],
                                         seat["column"], seat["row"]))
        for before, after in zip(seats, seats[1:]):
            if after["student_id"] <= before["student_id"]:
                texts.append(f"{paper_id} on {slot_text(slot)}: "
                             f"{after['student_id']} ({after['where']}) comes "
                             f"after {before['student_id']} "
                             f"({before['where']}).")
                break
    return texts


def room_contents(good_seats, data):
    """{(slot, room_id): set of (paper_id, section_id) seated there}."""
    contents = {}
    for seat in good_seats:
        pair = (seat["paper_id"], data["section_of"][seat["student_id"]])
        contents.setdefault((seat["slot"], seat["room_id"]), set()).add(pair)
    return contents


def check_duties(duty_rows, rooms_of_bad_rows, room_files, data, slot_of,
                 doubtful, good_seats, problems):
    """Rules 18 to 22: one duty per slot, teachers per room, never with
    their own students, a duty for each paper they teach. Each teacher in a
    slot is reported at most once. Papers in `doubtful` get no own-paper
    check: their real slot is not known."""
    contents = room_contents(good_seats, data)
    papers_in_room = {}
    for seat in good_seats:
        papers_in_room.setdefault((seat["slot"], seat["room_id"]),
                                  set()).add(seat["paper_id"])

    rows_of_teacher = {}           # (slot, teacher_id) -> [row, ...]
    teachers_of_room = {}          # (slot, room_id) -> {teacher_id}
    for row in duty_rows:
        slot = (row["_day"], row["_session"])
        rows_of_teacher.setdefault((slot, row["teacher_id"]), []).append(row)
        teachers_of_room.setdefault((slot, row["room_id"]),
                                    set()).add(row["teacher_id"])

    reported = set()               # (slot, teacher_id)
    for (slot, teacher_id), rows in sorted(rows_of_teacher.items()):
        if len(rows) > 1:
            rooms = ", ".join(row["room_id"] for row in rows)
            numbers = ", ".join(str(row["_row"]) for row in rows)
            problems.add("one duty per slot",
                         f"{teacher_id} has {len(rows)} duties on "
                         f"{slot_text(slot)} ({rooms}; duties.csv rows "
                         f"{numbers}).")
            reported.add((slot, teacher_id))

    for room_file in room_files:
        key = (room_file["slot"], room_file["room_id"])
        if key in rooms_of_bad_rows:
            continue
        teachers = sorted(teachers_of_room.get(key, set()))
        if len(teachers) != data["per_room"]:
            names = ", ".join(teachers) or "none"
            problems.add("teachers per room",
                         f"{room_file['room_id']} on "
                         f"{slot_text(room_file['slot'])} has "
                         f"{len(teachers)} teacher(s) ({names}); it needs "
                         f"{data['per_room']}.")

    for (slot, teacher_id), rows in sorted(rows_of_teacher.items()):
        if (slot, teacher_id) in reported:
            continue
        teaches = data["teaches"].get(teacher_id, set())
        for row in rows:
            own = sorted(contents.get((slot, row["room_id"]), set()) & teaches)
            if own:
                paper_id, section_id = own[0]
                problems.add("own students",
                             f"duties.csv row {row['_row']}: {teacher_id} is "
                             f"in {row['room_id']} on {slot_text(slot)}, with "
                             f"their own students ({paper_id}, {section_id}).")
                reported.add((slot, teacher_id))
                break

    # Rules 21 and 22, the same rule duties.py uses: a teacher (not a PhD
    # scholar) needs a duty in their paper's slot, in a room with their
    # paper and none of their own students; if no room is like that, in a
    # room without their paper and with none of their own students.
    rooms_in_slot = {}
    for room_file in room_files:
        rooms_in_slot.setdefault(room_file["slot"],
                                 []).append(room_file["room_id"])
    for teacher_id in sorted(data["teaches"]):
        if data["rank_of"].get(teacher_id) == PHD:
            continue
        teaches = data["teaches"][teacher_id]
        for paper_id in sorted({pair[0] for pair in teaches}):
            if paper_id not in slot_of or paper_id in doubtful:
                continue
            slot = slot_of[paper_id]
            if (slot, teacher_id) in reported:
                continue
            with_paper = []
            without_paper = []
            for room_id in rooms_in_slot.get(slot, []):
                if contents.get((slot, room_id), set()) & teaches:
                    continue
                if paper_id in papers_in_room.get((slot, room_id), set()):
                    with_paper.append(room_id)
                else:
                    without_paper.append(room_id)
            allowed = with_paper or without_paper
            duty_rooms = {row["room_id"]
                          for row in rows_of_teacher.get((slot, teacher_id),
                                                         [])}
            if duty_rooms & set(allowed):
                continue
            if not allowed:
                problems.add("own paper duty",
                             f"{teacher_id} teaches {paper_id} "
                             f"({slot_text(slot)}), but every room in that "
                             f"slot holds their own students.")
            else:
                now = (f"they are in {', '.join(sorted(duty_rooms))}"
                       if duty_rooms else "they have no duty then")
                problems.add("own paper duty",
                             f"{teacher_id} teaches {paper_id} "
                             f"({slot_text(slot)}) and needs a duty in one "
                             f"of {', '.join(allowed)}; {now}.")
            reported.add((slot, teacher_id))


# =============================================================== the check

def check_plan(data, folder):
    """All three stages. Returns (Problems, numbers for the summary line)."""
    problems = Problems()
    schedule_rows, duty_rows, room_files = read_plan(folder, data, problems)
    numbers = {"papers": len(schedule_rows), "room files": len(room_files),
               "duties": len(duty_rows)}
    if problems.count():
        return problems, numbers           # stage 1 failed: stop here

    # Stage 2
    slot_of, row_of, skipped = check_date_sheet(schedule_rows, data, problems)
    good_seats, bad_students, wrong_slot_papers, wrong_student = \
        check_seats_alone(room_files, data, slot_of, row_of, skipped,
                          problems)
    doubtful = skipped | wrong_slot_papers
    room_slots = {(room_file["slot"], room_file["room_id"])
                  for room_file in room_files}
    good_rows, rooms_of_bad_rows = check_duty_rows_alone(duty_rows, data,
                                                         room_slots, problems)

    # Stage 3
    for text in check_gap(data, slot_of, doubtful):
        problems.add("gap", text)
    reported = check_rooms(room_files, good_seats, problems)
    for text in check_seated_once(data, slot_of, good_seats, bad_students,
                                  wrong_student, reported):
        problems.add("seated once", text)
    for text in check_roll_order(data, slot_of, good_seats, reported):
        problems.add("roll order", text)
    check_duties(good_rows, rooms_of_bad_rows, room_files, data, slot_of,
                 doubtful, good_seats, problems)
    numbers["seats"] = len(good_seats)
    return problems, numbers


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check a plan folder against the rules.")
    parser.add_argument("input_dir", help="the input folder the plan was "
                                          "made from, e.g. data/tiny")
    parser.add_argument("plan_dir", help="a plan folder written by main.py, "
                                         "e.g. output/<timestamp>")
    args = parser.parse_args(argv)

    try:
        data = load_input(args.input_dir)
        folder = Path(args.plan_dir)
        if not folder.is_dir():
            raise CannotCheck(f"the plan folder {folder} doesn't exist.")
    except CannotCheck as reason:
        print(f"Can't check: {reason}")
        return 1

    why = folder / "why.txt"
    if why.is_file() and not (folder / "schedule.csv").exists():
        print("No plan in this folder, nothing to check. why.txt says:\n")
        print(why.read_text(encoding="utf-8", errors="replace").rstrip())
        return 2

    problems, numbers = check_plan(data, folder)
    if problems.count():
        print(problems.report())
        if any(problems.by_rule[rule] for rule in STAGE_1_RULES):
            print("\nFix these first. The other rules are checked once every "
                  "plan file can be read.")
        return 3
    print(f"Plan check: no problems. {numbers['papers']} papers, "
          f"{numbers['room files']} room files, {numbers['seats']} seats, "
          f"{numbers['duties']} duties checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

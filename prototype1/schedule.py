"""Step 4: give every paper a date and a session (model spec section 8).

This module only SCHEDULES. It reads the dict that loader.load() gives back,
and it assumes validate.check_data() found no problems.

How it works (decided in step 4, 2026-10-28):

  1. Papers.   Merge each same_paper group into one paper. Its ID is the
               group's first code. Every other code is its own paper.
  2. Clashes.  Two papers clash if at least one student writes both.
  3. Days.     Exam days are inside the window, on an exam weekday, and
               not a holiday.
  4. Limits.   A session holds at most the "one paper per room" seats:
               every room uses every other seat column (S: 12, M: 21).
               It also needs rooms x invigilators_per_room teachers.
  5. Place.    Papers go biggest first (most students; ties by paper ID).
               Each paper gets the EARLIEST exam day that is at least
               min_gap_days away from every paper it clashes with and has
               a session it fits in. If both sessions fit, it goes in the
               EMPTIER one; on a tie, the first session (morning).

Because no student ever has two papers on one day, the session choice can
never cause a clash. It only balances seats between morning and evening.
"""

import datetime
from dataclasses import dataclass, field

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Paper:
    paper_id: str
    course_codes: list                         # in the order first seen
    students: set = field(default_factory=set)


@dataclass
class Placement:
    date: datetime.date
    session: str
    paper: Paper


class NoPlan(Exception):
    """Raised when no schedule is possible. str(error) is the reason."""


# ---------------------------------------------------------------- 1. papers

def build_papers(data):
    """Returns {paper_id: Paper}. Every course code belongs to one paper."""
    paper_of_code = {}
    groups = data["constraints"].get("same_paper") or []
    for group in groups:
        codes = [str(code) for code in group]
        for code in codes:
            paper_of_code[code] = codes[0]

    papers = {}
    for course in data["courses"]:
        code = course["course_code"]
        paper_id = paper_of_code.get(code, code)
        if paper_id not in papers:
            papers[paper_id] = Paper(paper_id, [])
        papers[paper_id].course_codes.append(code)

    for registration in data["registrations"]:
        paper_id = paper_of_code.get(registration["course_code"],
                                     registration["course_code"])
        papers[paper_id].students.add(registration["student_id"])
    return papers


# ---------------------------------------------------------------- 2. clashes

def build_clashes(papers):
    """Returns {paper_id: set of paper_ids that share a student with it}."""
    papers_of_student = {}
    for paper in papers.values():
        for student in paper.students:
            papers_of_student.setdefault(student, set()).add(paper.paper_id)

    clashes = {paper_id: set() for paper_id in papers}
    for student_papers in papers_of_student.values():
        for paper_id in student_papers:
            clashes[paper_id] |= student_papers - {paper_id}
    return clashes


# ---------------------------------------------------------------- 3. days

def to_date(value):
    """settings.yaml dates arrive as date objects or 'YYYY-MM-DD' text."""
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def exam_days(settings):
    """Every date that can hold exams, in calendar order."""
    start = to_date(settings["start_date"])
    end = to_date(settings["end_date"])
    weekdays = set(settings["exam_weekdays"])
    holidays = {to_date(day) for day in (settings["holidays"] or [])}

    days = []
    day = start
    while day <= end:
        if WEEKDAY_NAMES[day.weekday()] in weekdays and day not in holidays:
            days.append(day)
        day += datetime.timedelta(days=1)
    return days


# ---------------------------------------------------------------- 4. limits

def one_paper_seats(room):
    """Seats a room gives when it holds one paper: every other seat column
    (columns 1, 3, 5, ...), all rows. S (6 x 3) gives 12, M (7 x 6) gives 21."""
    columns_used = (int(room["seat_columns"]) + 1) // 2
    return int(room["rows"]) * columns_used


def rooms_needed(students, rooms):
    """Estimate how many rooms a session opens: rooms in rooms.csv order until
    their one-paper seats cover the students. Step 5 does the real seating."""
    seats = 0
    count = 0
    for room in rooms:
        if seats >= students:
            break
        seats += one_paper_seats(room)
        count += 1
    return count


def session_fits(students, rooms, seat_limit, teacher_count, per_room):
    """Can one session hold this many students, by seats and by teachers?"""
    if students > seat_limit:
        return False
    return rooms_needed(students, rooms) * per_room <= teacher_count


# ---------------------------------------------------------------- 5. place

def make_schedule(data):
    """Returns a list of Placements, sorted by date, session and paper ID.
    Raises NoPlan with a short reason if some paper cannot be placed."""
    settings = data["settings"]
    sessions = [str(name) for name in settings["sessions"]]
    gap = settings["min_gap_days"]
    per_room = settings["invigilators_per_room"]
    rooms = data["rooms"]
    teacher_count = len(data["teachers"])
    seat_limit = sum(one_paper_seats(room) for room in rooms)

    papers = build_papers(data)
    clashes = build_clashes(papers)
    days = exam_days(settings)
    if not days:
        raise NoPlan("No plan possible.\n"
                     "Rule: exam days\n"
                     "settings.yaml gives no exam day: check the window, "
                     "exam_weekdays and holidays.")

    date_of = {}                                    # paper_id -> date
    load = {(day, s): 0 for day in days for s in sessions}   # students
    placements = []

    order = sorted(papers.values(),
                   key=lambda paper: (-len(paper.students), paper.paper_id))
    for paper in order:
        size = len(paper.students)
        blocked_by_gap = 0
        blocked_by_room = 0
        placed = False
        for day in days:
            too_close = any(abs((day - date_of[other]).days) < gap
                            for other in clashes[paper.paper_id]
                            if other in date_of)
            if too_close:
                blocked_by_gap += 1
                continue
            fitting = [s for s in sessions
                       if session_fits(load[(day, s)] + size, rooms,
                                       seat_limit, teacher_count, per_room)]
            if not fitting:
                blocked_by_room += 1
                continue
            # Emptier session first; min() keeps the first one on a tie.
            session = min(fitting, key=lambda s: load[(day, s)])
            date_of[paper.paper_id] = day
            load[(day, session)] += size
            placements.append(Placement(day, session, paper))
            placed = True
            break
        if not placed:
            raise NoPlan(
                "No plan possible.\n"
                f"Paper: {paper.paper_id} ({size} students)\n"
                f"Of {len(days)} exam days, {blocked_by_gap} break the gap "
                f"rule (a clashing paper is less than {gap} days away) and "
                f"{blocked_by_room} have no session with room for it "
                f"(limit {seat_limit} seats and {teacher_count} teachers "
                f"per session).")

    placements.sort(key=lambda p: (p.date, sessions.index(p.session),
                                   p.paper.paper_id))
    return placements


def fullest_session(placements, data):
    """(date, session, students, seat_limit) of the session with the most
    students, so a run shows how close the plan is to the seat limit.
    None if nothing was scheduled."""
    if not placements:
        return None
    load = {}
    for placement in placements:
        key = (placement.date, placement.session)
        load[key] = load.get(key, 0) + len(placement.paper.students)
    (day, session), students = max(load.items(), key=lambda item: item[1])
    seat_limit = sum(one_paper_seats(room) for room in data["rooms"])
    return day, session, students, seat_limit

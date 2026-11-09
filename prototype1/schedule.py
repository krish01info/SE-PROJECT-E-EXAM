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
               Then step 5 is ASKED: a paper goes into a session only if
               seat.seat_slot() can really seat that session with it, and
               the rooms it opens x invigilators_per_room is at most the
               number of teachers. (2026-11-03, Krish: counting seats alone
               let 9 Nov evening take 590 students that one paper per room
               could not seat.)
               Last, the duty rule is ASKED (duties.py): every teacher of
               every paper in the session must have a room they may take
               for their paper. (2026-11-03, Krish: check before booking,
               so the error is stopped early; e.g. HUM2001 alone in a slot
               left its teacher no room.)
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

import duties
import seat
from errors import NoPlan

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


def teacher_room_check(papers, limits):
    """The papers_short function seat.seat_slot() uses for these papers:
    given RoomPlans, the IDs of papers with a teacher (not a PhD scholar)
    who has no room they may invigilate (model spec section 10)."""
    def papers_short(plans):
        missing = duties.teachers_without_room(
            papers, plans, limits["teaching"], limits["rank_of"],
            limits["section_of"])
        return {paper_id for _, paper_id in missing}
    return papers_short


def room_check_for(data):
    """For seat.make_seating(): given a slot's papers, its teacher check.
    main.py uses this so step 5 seats each slot exactly as step 4 checked."""
    limits = session_limits(data, build_papers(data))
    return lambda papers: teacher_room_check(papers, limits)


def session_problem(papers, rooms, limits):
    """Can one session hold these papers? Returns None if yes, otherwise
    the first check that fails: "seats" (more students than the one-paper
    seats, or step 5 can't seat them), "teachers" (too few teachers for the
    rooms) or "duty room" (a teacher has no room for their paper).
    `limits` is the dict from session_limits()."""
    students = sum(len(paper.students) for paper in papers)
    if students > limits["seat_limit"]:
        return "seats"
    try:
        plans = seat.seat_slot(papers, rooms, limits["section_of"],
                               teacher_room_check(papers, limits))
    except NoPlan:
        return "seats"
    if len(plans) * limits["per_room"] > limits["teacher_count"]:
        return "teachers"
    if duties.teachers_without_room(papers, plans, limits["teaching"],
                                    limits["rank_of"], limits["section_of"]):
        return "duty room"
    return None


def session_fits(papers, rooms, limits):
    """True if session_problem() finds nothing wrong."""
    return session_problem(papers, rooms, limits) is None


def session_limits(data, papers):
    """Everything session_problem() needs that is the same for every
    session: built once per run."""
    rooms = data["rooms"]
    return {
        "seat_limit": sum(one_paper_seats(room) for room in rooms),
        "per_room": data["settings"]["invigilators_per_room"],
        "teacher_count": len(data["teachers"]),
        "teaching": duties.build_teaching(data, papers),
        "rank_of": {teacher["teacher_id"]: teacher["rank"]
                    for teacher in data["teachers"]},
        "section_of": duties.section_of_student(data),
    }


# ---------------------------------------------------------------- 0. cheap checks

def most_papers_in_window(days, gap):
    """The most papers one student can write on these exam days, with at
    least `gap` days between any two: take the first day, then the first
    day at least `gap` days later, and so on."""
    count = 0
    last = None
    for day in days:
        if last is None or (day - last).days >= gap:
            count += 1
            last = day
    return count


def check_before_scheduling(papers, days, gap, seat_limit, room_count):
    """Cheap checks run before scheduling (model spec section 12). Each one
    shows straight away that no plan can exist. Raises NoPlan."""
    # 1. A student with more papers than the window can hold.
    papers_of = {}
    for paper in papers.values():
        for student in paper.students:
            papers_of.setdefault(student, []).append(paper.paper_id)
    most = most_papers_in_window(days, gap)
    too_many = sorted(student for student, paper_ids in papers_of.items()
                      if len(paper_ids) > most)
    if too_many:
        first = too_many[0]
        names = ", ".join(sorted(papers_of[first]))
        raise NoPlan(
            "No plan possible.\n"
            "Rule: gap\n"
            f"Student: {first} writes {len(papers_of[first])} papers "
            f"({names}).\n"
            f"The window has {len(days)} exam days ({days[0]} to "
            f"{days[-1]}). With at least {gap} days between two papers of a "
            f"student, at most {most} papers fit.\n"
            f"Students with more papers than that: {len(too_many)}.")

    # 2. A paper bigger than all the rooms together, one paper per room.
    #    A paper alone can't use neighbouring columns, so this is the most
    #    seats it can ever get in one session.
    if papers:
        biggest = max(papers.values(),
                      key=lambda paper: (len(paper.students), paper.paper_id))
        if len(biggest.students) > seat_limit:
            raise NoPlan(
                "No plan possible.\n"
                "Rule: seats\n"
                f"Paper: {biggest.paper_id} ({len(biggest.students)} "
                f"students)\n"
                f"All {room_count} rooms together give {seat_limit} seats to "
                f"one paper (every other seat column), so no session can "
                f"seat it.")


# ---------------------------------------------------------------- 5. place

def make_schedule(data):
    """Returns a list of Placements, sorted by date, session and paper ID.
    Raises NoPlan with a short reason if some paper cannot be placed."""
    settings = data["settings"]
    sessions = [str(name) for name in settings["sessions"]]
    gap = settings["min_gap_days"]
    rooms = data["rooms"]

    papers = build_papers(data)
    limits = session_limits(data, papers)
    clashes = build_clashes(papers)
    days = exam_days(settings)
    if not days:
        raise NoPlan("No plan possible.\n"
                     "Rule: exam days\n"
                     "settings.yaml gives no exam day: check the window, "
                     "exam_weekdays and holidays.")
    check_before_scheduling(papers, days, gap, limits["seat_limit"],
                            len(rooms))

    date_of = {}                                    # paper_id -> date
    load = {(day, s): 0 for day in days for s in sessions}   # students
    papers_in = {(day, s): [] for day in days for s in sessions}
    placements = []

    def too_close(paper, day):
        return any(abs((day - date_of[other]).days) < gap
                   for other in clashes[paper.paper_id] if other in date_of)

    def problem(slot, extra):
        return session_problem(papers_in[slot] + extra, rooms, limits)

    def place(paper, slot):
        date_of[paper.paper_id] = slot[0]
        load[slot] += len(paper.students)
        papers_in[slot].append(paper)
        placements.append(Placement(slot[0], slot[1], paper))

    order = sorted(papers.values(),
                   key=lambda paper: (-len(paper.students), paper.paper_id))
    for paper in order:
        size = len(paper.students)
        free_days = [day for day in days if not too_close(paper, day)]
        blocked_by_gap = len(days) - len(free_days)

        # 1. A session waiting for another paper comes first, if this paper
        #    fixes it (Krish: waiting, because we have to take the paper).
        waiting = [(day, s) for day in free_days for s in sessions
                   if papers_in[(day, s)]
                   and problem((day, s), []) == "duty room"
                   and problem((day, s), [paper]) is None]
        if waiting:
            place(paper, waiting[0])
            continue

        # 2. Otherwise the earliest day with a session it fits in, the
        #    emptier one first. If it fits nowhere only because it would be
        #    alone and a teacher needs another paper's room, it may wait in
        #    an empty session.
        blocked = {"seats": 0, "teachers": 0, "duty room": 0}
        placed = False
        for day in free_days:
            problems = {s: problem((day, s), [paper]) for s in sessions}
            fitting = [s for s in sessions if problems[s] is None]
            if fitting:
                # min() keeps the first session (morning) on a tie.
                place(paper, (day, min(fitting, key=lambda s: load[(day, s)])))
                placed = True
                break
            can_wait = [s for s in sessions
                        if problems[s] == "duty room" and not papers_in[(day, s)]]
            if can_wait:
                place(paper, (day, can_wait[0]))
                placed = True
                break
            # Count every session of the day under its own problem.
            for s in sessions:
                blocked[problems[s]] += 1
        if not placed:
            open_days = len(free_days)
            raise NoPlan(
                "No plan possible.\n"
                "Rule: paper placement\n"
                f"Paper: {paper.paper_id} ({size} students)\n"
                f"No exam day can take it. Every reason, of {len(days)} "
                f"exam days:\n"
                f"- gap rule: {blocked_by_gap} days are less than {gap} days "
                f"from a paper that shares students with it\n"
                f"- on the other {open_days} days "
                f"({open_days * len(sessions)} sessions):\n"
                f"  - seats: {blocked['seats']} sessions have no seats left "
                f"for it (at most {limits['seat_limit']} seats, one paper per "
                f"room, two in a room only when rooms run out)\n"
                f"  - teachers: {blocked['teachers']} sessions would need more "
                f"teachers than the {limits['teacher_count']} there are "
                f"({limits['per_room']} per room)\n"
                f"  - duty room: {blocked['duty room']} sessions would leave a "
                f"teacher of a paper with no room to invigilate")

    # 3. Last check: a session still waiting for another paper means no plan.
    for slot in sorted(papers_in, key=lambda s: (s[0], sessions.index(s[1]))):
        if papers_in[slot] and problem(slot, []) == "duty room":
            plans = seat.seat_slot(papers_in[slot], rooms, limits["section_of"],
                                   teacher_room_check(papers_in[slot], limits))
            missing = duties.teachers_without_room(
                papers_in[slot], plans, limits["teaching"], limits["rank_of"],
                limits["section_of"])
            names = ", ".join(f"{teacher} ({paper_id})"
                              for teacher, paper_id in missing)
            raise NoPlan(
                "No plan possible.\n"
                "Rule: duty room\n"
                f"Slot: {slot[0]} {slot[1]}\n"
                f"Papers: {', '.join(p.paper_id for p in papers_in[slot])}. "
                f"No other paper could join this slot, so these teachers "
                f"have no room they may invigilate for their paper: {names}.")

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

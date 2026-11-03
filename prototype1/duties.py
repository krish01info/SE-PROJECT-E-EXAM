"""Duty rules (model spec section 10).

It holds the rule that step 4 asks before it books a session, and
step 6, make_duties(), which gives every room its teachers.

The rule for a teacher's own paper (2026-11-03, Krish):

  Every teacher who teaches a paper (PhD scholars are exempt) needs one
  room in that paper's slot that they are allowed to invigilate:

    1. first choice: a room WITH their paper and none of their own students;
    2. if there is no such room: a room in the same slot WITHOUT their paper
       and with none of their own students, so they are nearby if the
       question paper has a mistake (the 2026-10-22 team rule, widened).

  "Their own students" are the students of every section they teach, for
  any paper written in that room (teaching.csv: teacher, code, section).
"""

from errors import NoPlan

PHD = "PHD"


def build_teaching(data, papers):
    """{teacher_id: set of (paper_id, section_id)} from teaching.csv.
    `papers` is schedule.build_papers(data), used to turn a course code
    into its paper ID."""
    paper_of_code = {code: paper.paper_id
                     for paper in papers.values()
                     for code in paper.course_codes}
    teaching = {}
    for row in data["teaching"]:
        pair = (paper_of_code[row["course_code"]], row["section_id"])
        teaching.setdefault(row["teacher_id"], set()).add(pair)
    return teaching


def section_of_student(data):
    """{student_id: section_id}."""
    return {student["student_id"]: student["section_id"]
            for student in data["students"]}


def room_contents(plan, section_of):
    """The (paper_id, section_id) pairs seated in one room (a RoomPlan)."""
    return {(cell[0], section_of[cell[1]])
            for row in plan.grid for cell in row if cell}


def paper_duty_rooms(paper_id, teaches, plans, section_of):
    """The rooms a teacher may take for their paper `paper_id`, as a list of
    room IDs: rule 1 if any room meets it, otherwise rule 2 (may be empty).
    `teaches` is that teacher's set of (paper_id, section_id); `plans` are
    the RoomPlans of the paper's slot."""
    with_paper = []
    without_paper = []
    for plan in plans:
        contents = room_contents(plan, section_of)
        if contents & teaches:
            continue                      # never with their own students
        if paper_id in plan.papers:
            with_paper.append(plan.room_id)
        else:
            without_paper.append(plan.room_id)
    return with_paper if with_paper else without_paper


def teachers_without_room(papers, plans, teaching, rank_of, section_of):
    """Check one slot. `papers` are the papers written in it and `plans`
    its RoomPlans. Returns a sorted list of (teacher_id, paper_id) for every
    teacher (not a PhD scholar) who has no room they may take for that
    paper. An empty list means the rule holds."""
    in_slot = {paper.paper_id for paper in papers}
    missing = []
    for teacher_id in sorted(teaching):
        if rank_of.get(teacher_id) == PHD:
            continue
        teaches = teaching[teacher_id]
        for paper_id in sorted({pair[0] for pair in teaches} & in_slot):
            if not paper_duty_rooms(paper_id, teaches, plans, section_of):
                missing.append((teacher_id, paper_id))
    return missing


# ======================================================== step 6: duties
#
# make_duties() gives every room in every slot `invigilators_per_room`
# teachers (model spec section 10). Decisions (Krish, 2026-11-03):
#
#   - own-paper duties come first, in a room from paper_duty_rooms();
#   - every other place goes to the teacher with no duty in another session
#     that day (teachers also check copies and have other work), then the
#     fewest duties so far, then the lower teacher ID;
#   - if a teacher can't get a place because the rooms they may sit in are
#     full, a chain of moves is tried (someone in that room moves to another
#     room they may sit in, and so on), so a plan is found whenever one
#     exists: "no solution" is not an option when there is one;
#   - PhD scholars come last, so they are picked only when no other teacher
#     can be placed ("let's not disturb the PhD scholars").


class SlotDuties:
    """Who sits in which room in one slot, while the slot is being filled."""

    def __init__(self, plans, per_room):
        self.order = [plan.room_id for plan in plans]    # rooms.csv order
        self.per_room = per_room
        self.teachers_in = {room_id: [] for room_id in self.order}
        self.room_of = {}

    def has_free_place(self, room_id):
        return len(self.teachers_in[room_id]) < self.per_room

    def all_full(self):
        return not any(self.has_free_place(room_id) for room_id in self.order)

    def put(self, teacher_id, room_id):
        self.teachers_in[room_id].append(teacher_id)
        self.room_of[teacher_id] = room_id

    def take_out(self, teacher_id):
        room_id = self.room_of.pop(teacher_id)
        self.teachers_in[room_id].remove(teacher_id)
        return room_id


def place_teacher(teacher_id, state, may_sit, rooms_tried):
    """Give teacher_id a place in a room they may sit in (first such room
    with a free place, in rooms.csv order).

    If all those rooms are full: take a teacher out of one of them, put
    teacher_id in, and try to place the one taken out in another room they
    may sit in, the same way (a chain of moves). Every teacher who had a
    place still has one afterwards, only maybe in another room.

    Returns True if it worked. On False nothing has changed. `rooms_tried`
    is the set of rooms already used in this chain, so it can't go round in
    circles."""
    rooms = [room_id for room_id in state.order if may_sit(teacher_id, room_id)]
    for room_id in rooms:
        if state.has_free_place(room_id):
            state.put(teacher_id, room_id)
            return True
    for room_id in rooms:
        if room_id in rooms_tried:
            continue
        rooms_tried.add(room_id)
        for other in list(state.teachers_in[room_id]):
            state.take_out(other)
            state.put(teacher_id, room_id)
            if place_teacher(other, state, may_sit, rooms_tried):
                return True
            state.take_out(teacher_id)            # undo: put it back
            state.put(other, room_id)
    return False


def best_first(teacher_ids, day, counts, days_worked):
    """Teachers in the order they are picked for a place: no duty yet on
    `day` first, then fewest duties so far, then teacher ID (Krish's order
    (i): avoiding a second shift on one day comes before equal totals)."""
    return sorted(teacher_ids,
                  key=lambda teacher_id: (day in days_worked.get(teacher_id, ()),
                                          counts[teacher_id], teacher_id))


def no_plan(rule, day, session, text):
    return NoPlan(f"No plan possible.\nRule: {rule}\n"
                  f"Slot: {day} {session}\n{text}")


def own_paper_rooms(teacher_id, teaches, plans, section_of, day, session):
    """The rooms that count as teacher_id's own-paper duty in this slot, as a
    set, or None if no paper they teach is written in this slot. A teacher
    has one duty per slot, so if two of their papers are in this slot, one
    room must count for both. Raises NoPlan if no room counts."""
    papers_here = {paper_id for plan in plans for paper_id in plan.papers}
    own_papers = sorted({pair[0] for pair in teaches} & papers_here)
    if not own_papers:
        return None
    rooms = {plan.room_id for plan in plans}
    for paper_id in own_papers:
        rooms &= set(paper_duty_rooms(paper_id, teaches, plans, section_of))
    if not rooms:
        if len(own_papers) == 1:
            text = (f"{teacher_id} needs a duty for {own_papers[0]}, but every "
                    f"room in this slot has their own students.")
        else:
            text = (f"{teacher_id} teaches {', '.join(own_papers)}, all written "
                    f"in this slot, and no one room counts as a duty for all "
                    f"of them (a teacher has at most one duty per slot).")
        raise no_plan("duty room", day, session, text)
    return rooms


def staff_slot(day, session, plans, teaching, regulars, phds, per_room,
               counts, days_worked, section_of):
    """Fill every room of one slot with `per_room` teachers. Returns the
    SlotDuties. Raises NoPlan if it can't be done."""
    contents = {plan.room_id: room_contents(plan, section_of) for plan in plans}

    allowed = {}       # teacher -> rooms without their own students
    must = {}          # teacher -> rooms that count as their own-paper duty
    for teacher_id in regulars + phds:
        teaches = teaching.get(teacher_id, set())
        allowed[teacher_id] = {room_id for room_id, inside in contents.items()
                               if not inside & teaches}
        if teacher_id in regulars:                  # PhD scholars are exempt
            rooms = own_paper_rooms(teacher_id, teaches, plans, section_of,
                                    day, session)
            if rooms is not None:
                must[teacher_id] = rooms

    def may_sit(teacher_id, room_id):
        if teacher_id in must:
            return room_id in must[teacher_id]
        return room_id in allowed[teacher_id]

    state = SlotDuties(plans, per_room)

    # 1. Own-paper duties. Teachers with the fewest rooms go first.
    for teacher_id in sorted(must, key=lambda t: (len(must[t]), t)):
        if not place_teacher(teacher_id, state, may_sit, set()):
            rooms = ", ".join(r for r in state.order if r in must[teacher_id])
            raise no_plan("duty room", day, session,
                          f"{teacher_id} needs a duty in one of {rooms} for "
                          f"their own paper, but those rooms are full of "
                          f"other teachers who can't sit anywhere else.")

    # 2. Every other place: regular teachers best first, PhD scholars last.
    others = (best_first([t for t in regulars if t not in must], day,
                         counts, days_worked)
              + best_first(phds, day, counts, days_worked))
    for teacher_id in others:
        if state.all_full():
            break
        place_teacher(teacher_id, state, may_sit, set())

    if not state.all_full():
        short = ", ".join(f"{room_id} has {len(state.teachers_in[room_id])}"
                          for room_id in state.order
                          if state.has_free_place(room_id))
        needed = per_room * len(plans)
        raise no_plan("duties", day, session,
                      f"Every room needs {per_room} teachers. Short: {short}.\n"
                      f"Needs {needed} teachers, {len(state.room_of)} could be "
                      f"placed ({len(regulars)} regular teachers, {len(phds)} "
                      f"PhD scholars; nobody sits with their own students or "
                      f"has two duties in one slot).")
    return state


def make_duties(seating, data, papers):
    """Step 6. `seating` is seat.make_seating()'s {(date, session):
    [RoomPlan]}, `papers` is schedule.build_papers(data). Slots are done in
    date order, morning before evening, so "fewest duties so far" and "a
    duty already on this day" count the slots before.

    Returns a list of (date, session, room_id, teacher_id), slot by slot,
    rooms in rooms.csv order, teachers of a room by ID. Raises NoPlan if a
    room can't get its teachers."""
    settings = data["settings"]
    per_room = int(settings["invigilators_per_room"])
    sessions = [str(name) for name in settings["sessions"]]
    teaching = build_teaching(data, papers)
    section_of = section_of_student(data)
    regulars = sorted(t["teacher_id"] for t in data["teachers"]
                      if t["rank"] != PHD)
    phds = sorted(t["teacher_id"] for t in data["teachers"]
                  if t["rank"] == PHD)

    counts = {teacher_id: 0 for teacher_id in regulars + phds}
    days_worked = {}                                # teacher -> set of dates
    rows = []
    for day, session in sorted(seating, key=lambda slot: (slot[0],
                                                          sessions.index(slot[1]))):
        state = staff_slot(day, session, seating[(day, session)], teaching,
                           regulars, phds, per_room, counts, days_worked,
                           section_of)
        for room_id in state.order:
            for teacher_id in sorted(state.teachers_in[room_id]):
                rows.append((day, session, room_id, teacher_id))
                counts[teacher_id] += 1
                days_worked.setdefault(teacher_id, set()).add(day)
    return rows


def duty_summary(rows, data):
    """Numbers main.py prints: fewest and most duties of a regular teacher,
    duties of PhD scholars, and teacher-days with more than one shift."""
    rank_of = {t["teacher_id"]: t["rank"] for t in data["teachers"]}
    counts = {teacher_id: 0 for teacher_id in rank_of}
    shifts = {}
    for day, _session, _room_id, teacher_id in rows:
        counts[teacher_id] += 1
        shifts[(teacher_id, day)] = shifts.get((teacher_id, day), 0) + 1
    regular_counts = [n for t, n in counts.items() if rank_of[t] != PHD]
    return {
        "fewest": min(regular_counts) if regular_counts else 0,
        "most": max(regular_counts) if regular_counts else 0,
        "phd_duties": sum(n for t, n in counts.items() if rank_of[t] == PHD),
        "double_days": sum(1 for n in shifts.values() if n > 1),
    }

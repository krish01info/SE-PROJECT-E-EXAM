"""Step 5: give every student a seat (model spec section 9).

This module only SEATS. It takes the placements from schedule.make_schedule()
and the rooms from rooms.csv, and gives back a picture of every room in use
in every slot.

How it works (redone 2026-11-03, Krish's decision: one paper per room, as
our university does it, and two papers in a room only when needed):

  1. Order.   In each slot, every paper's students are sorted by student_id
              (roll order). All sections of a paper are one queue. Papers go
              biggest first (most students), ties by paper ID.
  2. Alone.   Each paper gets its own rooms, in rooms.csv order. It sits in
              the odd seat columns only (1, 3, 5, ...), so no two neighbouring
              columns hold the same paper. S holds 12, M holds 21.
              If every paper fits this way, that is the plan.
              Sections: if starting each section of a paper in a new room
              needs no more rooms for that paper than filling straight on,
              each section starts in a new room. (2026-11-03, Krish: in
              real life we can't change the data, so the seating must give
              each section's teacher a room without their own students.)
  3. Mix.     Only if the rooms run out:
              a. Each paper first fills, alone, the rooms it fills COMPLETELY.
                 Its last students, too few to fill a room, are its "leftover".
              b. The leftovers go into the rooms still free, in rooms.csv
                 order. The biggest leftover takes the odd columns. A second
                 leftover joins it in the even columns ONLY if, without that,
                 the leftovers still waiting would be more than the free rooms
                 after this one. The partner is the biggest leftover that fits
                 completely in the even columns (if none fits, the biggest).
              A room never holds a third paper. Each paper's leftover sits in
              a later room than the rest of it, so roll order is kept.
  4. No plan. If students are still left when the rooms run out, it raises
              NoPlan and nothing is written.

A room CSV shows the room as the invigilator at the front sees it: row 1 is
the front row, column 1 is on the left.
"""

from dataclasses import dataclass

from errors import NoPlan


@dataclass
class RoomPlan:
    room_id: str
    papers: list        # paper IDs in this room: one or two
    grid: list          # grid[row][column] = (paper_id, student_id) or None


# ---------------------------------------------------------------- one room

def odd_columns(room):
    """Column numbers 0, 2, 4, ... (columns 1, 3, 5 ... as people count)."""
    return list(range(0, int(room["seat_columns"]), 2))


def even_columns(room):
    """Column numbers 1, 3, 5, ... (columns 2, 4, 6 ... as people count)."""
    return list(range(1, int(room["seat_columns"]), 2))


def alone_seats(room):
    """Seats of one paper alone: the odd columns. S gives 12, M gives 21."""
    return int(room["rows"]) * len(odd_columns(room))


def partner_seats(room):
    """Seats of a second paper: the even columns. S gives 6, M gives 21."""
    return int(room["rows"]) * len(even_columns(room))


def fill_columns(grid, columns, paper_id, students):
    """Seat students (in order) down each column, front to back. Removes the
    seated students from the front of `students`."""
    for column in columns:
        for row in grid:
            if not students:
                return
            row[column] = (paper_id, students.pop(0))


def seat_room(room, groups):
    """Fill one room. `groups` is one or two [paper_id, students] pairs: the
    first gets the odd columns, the second the even columns. Students are
    taken from the front of each list. Returns a RoomPlan."""
    rows = int(room["rows"])
    columns = int(room["seat_columns"])
    grid = [[None] * columns for _ in range(rows)]

    first_id, first_students = groups[0]
    fill_columns(grid, odd_columns(room), first_id, first_students)
    papers = [first_id]
    if len(groups) == 2:
        second_id, second_students = groups[1]
        fill_columns(grid, even_columns(room), second_id, second_students)
        papers.append(second_id)
    return RoomPlan(room["room_id"], papers, grid)


# ---------------------------------------------------------------- one slot

def paper_queues(papers):
    """[paper_id, sorted students] for each paper with students, biggest
    first, ties by paper ID."""
    queues = [[paper.paper_id, sorted(paper.students)]
              for paper in papers if paper.students]
    queues.sort(key=lambda queue: (-len(queue[1]), queue[0]))
    return queues


def section_runs(students, section_of):
    """Split a sorted student list into runs of one section each, in order.
    With no section_of, the whole list is one run."""
    if not section_of:
        return [list(students)]
    runs = []
    for student in students:
        if runs and section_of[runs[-1][-1]] == section_of[student]:
            runs[-1].append(student)
        else:
            runs.append([student])
    return runs


def rooms_used(groups, rooms, first_index):
    """How many rooms, from rooms[first_index] on, the groups of students
    need if each group starts in a new room, alone. None if they run out."""
    index = first_index
    for group in groups:
        left = len(group)
        while left > 0:
            if index == len(rooms):
                return None
            left -= alone_seats(rooms[index])
            index += 1
    return index - first_index


def seat_alone(papers, rooms, section_of=None):
    """Point 2: one paper per room. Returns the RoomPlans, or None if the
    rooms run out. With section_of, a paper's sections each start in a new
    room when that needs no extra room for the paper."""
    plans = []
    room_index = 0
    for paper_id, students in paper_queues(papers):
        runs = section_runs(students, section_of)
        straight = rooms_used([students], rooms, room_index)
        by_section = rooms_used(runs, rooms, room_index)
        if straight is None:
            return None
        groups = runs if by_section == straight else [students]
        for group in groups:
            while group:
                plans.append(seat_room(rooms[room_index],
                                       [[paper_id, group]]))
                room_index += 1
    return plans


def pick_partner(leftovers, room):
    """The biggest leftover that fits completely in the room's even columns;
    if none fits, the biggest one. `leftovers` is sorted biggest first."""
    for leftover in leftovers:
        if len(leftover[1]) <= partner_seats(room):
            return leftover
    return leftovers[0]


def seat_with_mixing(papers, rooms):
    """Point 3: alone where a paper fills a room, leftovers mixed only where
    needed. Returns (RoomPlans, {paper_id: students still without a seat})."""
    plans = []
    leftovers = []
    room_index = 0

    # a. Rooms a paper fills completely, alone.
    for paper_id, students in paper_queues(papers):
        while (room_index < len(rooms)
               and len(students) >= alone_seats(rooms[room_index])):
            plans.append(seat_room(rooms[room_index], [[paper_id, students]]))
            room_index += 1
        if students:
            leftovers.append([paper_id, students])

    # b. Leftovers in the rooms still free.
    for index in range(room_index, len(rooms)):
        leftovers = [leftover for leftover in leftovers if leftover[1]]
        if not leftovers:
            break
        leftovers.sort(key=lambda leftover: (-len(leftover[1]), leftover[0]))
        room = rooms[index]
        free_rooms_after = len(rooms) - index - 1
        groups = [leftovers[0]]
        if len(leftovers) - 1 > free_rooms_after:
            groups.append(pick_partner(leftovers[1:], room))
        plans.append(seat_room(room, groups))

    unseated = {paper_id: students for paper_id, students in leftovers
                if students}
    return plans, unseated


def seat_slot(papers, rooms, section_of=None):
    """Seat one slot. `papers` are the schedule.Paper objects written in it.
    `section_of` is {student_id: section_id} (optional; tests without it get
    no section rule). Returns a list of RoomPlans, only for rooms in use, in
    rooms.csv order. Raises NoPlan if the rooms run out even with mixing."""
    plans = seat_alone(papers, rooms, section_of)
    if plans is not None:
        return plans

    plans, unseated = seat_with_mixing(papers, rooms)
    if unseated:
        total = sum(len(paper.students) for paper in papers)
        missing = sum(len(students) for students in unseated.values())
        # Backup (step 7): through main.py this never happens, because step 4
        # asks seat_slot() before booking a session. Kept so seat_slot() is
        # safe on its own; tested in tests/test_seat.py.
        names = ", ".join(f"{paper_id} ({len(students)})"
                          for paper_id, students in sorted(unseated.items()))
        raise NoPlan(
            "No plan possible.\n"
            "Rule: seats\n"
            f"All {len(rooms)} rooms are in use, with two papers in a room "
            f"where needed, but {missing} of {total} students still have no "
            f"seat: {names}.")
    return plans


def make_seating(placements, rooms, section_of=None):
    """Returns {(date, session): [RoomPlan, ...]}, slots in schedule order.
    Raises NoPlan (with the slot named) if any slot cannot be seated."""
    papers_of_slot = {}
    for placement in placements:
        slot = (placement.date, placement.session)
        papers_of_slot.setdefault(slot, []).append(placement.paper)

    seating = {}
    for (day, session), papers in papers_of_slot.items():
        try:
            seating[(day, session)] = seat_slot(papers, rooms, section_of)
        except NoPlan as reason:
            first_line, rest = str(reason).split("\n", 1)
            raise NoPlan(f"{first_line}\nSlot: {day} {session}\n{rest}")
    return seating


def cell_text(cell):
    """What a room CSV cell shows: 'PAPER:STUDENT', or blank for an empty
    seat (model spec section 11)."""
    if cell is None:
        return ""
    paper_id, student_id = cell
    return f"{paper_id}:{student_id}"

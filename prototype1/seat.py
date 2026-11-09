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
              Best combination (2026-11-09, Krish): before seating, the
              tool tries the combinations of room sizes for all papers of
              the slot together, and picks the one with the FEWEST ROOMS,
              then the fewest empty seats (see seat_best()). Each paper's
              chosen rooms are filled in rooms.csv order, so roll order is
              kept. If a teacher who teaches every section of a paper would
              then have no room without their own students, only that paper
              is split by section and the search runs again. If that can't
              seat the slot, the plain rooms.csv order above is tried
              (seat_alone()).
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


# ---------------------------------------------------- best room combination
#
# Added 2026-11-09 (Krish): rooms come in a few sizes (S holds 12 of one
# paper, M holds 21), so before seating anyone we try the combinations of
# room sizes and pick the one that uses the FEWEST ROOMS, then the fewest
# empty seats. Example: 45 students -> 1 M + 2 S (45 seats, none empty), not
# M + M + S (54 seats, 9 empty). The chosen rooms of a paper are then filled
# in rooms.csv order, so roll order stays as before.

MAX_STATES = 200_000    # safety limit for the search; past it, use the old way


def room_sizes(rooms):
    """The different one-paper sizes of the rooms, biggest first, and how
    many rooms there are of each: ([21, 12], [18, 18]) for main."""
    count_of = {}
    for room in rooms:
        size = alone_seats(room)
        if size > 0:
            count_of[size] = count_of.get(size, 0) + 1
    sizes = sorted(count_of, reverse=True)
    return sizes, [count_of[size] for size in sizes]


def room_options(students, sizes, available):
    """Every way to seat `students` people with rooms of these sizes (at most
    `available` of each), where no room could be left out. Each way is a
    tuple of room counts, one per size: (1, 2) = 1 M and 2 S."""
    options = []

    def build(index, counts, seats):
        if index == len(sizes) - 1:
            left = max(0, students - seats)
            last = -(-left // sizes[index])           # rounded up
            if last > available[index]:
                return
            option = tuple(counts + [last])
            total = seats + last * sizes[index]
            # No room may be spare: taking any one room out must not fit.
            if all(count == 0 or total - size < students
                   for count, size in zip(option, sizes)):
                options.append(option)
            return
        for count in range(available[index] + 1):
            build(index + 1, counts + [count], seats + count * sizes[index])
            if seats + count * sizes[index] >= students:
                break

    build(0, [], 0)
    return options


def fewest_rooms(students, sizes, available):
    """The fewest rooms that can seat `students` alone; None if none can."""
    options = room_options(students, sizes, available)
    return min((sum(option) for option in options), default=None)


def best_combination(groups, sizes, available):
    """Pick one room option for each group of students so that all groups
    fit in the rooms there are, with the fewest rooms in total, then the
    fewest empty seats. Returns one option per group, or None if they can't
    all fit (or the search would be too big)."""
    # state: rooms used of each size -> (rooms, empty seats, options so far)
    states = {tuple([0] * len(sizes)): (0, 0, ())}
    for group in groups:
        options = room_options(len(group), sizes, available)
        next_states = {}
        for used, (room_count, empty, chosen) in states.items():
            for option in options:
                now_used = tuple(u + o for u, o in zip(used, option))
                if any(u > a for u, a in zip(now_used, available)):
                    continue
                seats = sum(o * size for o, size in zip(option, sizes))
                value = (room_count + sum(option),
                         empty + seats - len(group), chosen + (option,))
                old = next_states.get(now_used)
                if old is None or value[:2] < old[:2]:
                    next_states[now_used] = value
        if not next_states or len(next_states) > MAX_STATES:
            return None
        states = next_states
    best = min(states.values(), key=lambda value: value[:2])
    return list(best[2])


def keeps_roll_order(room_lists, position):
    """True if each group's rooms all come before the next group's rooms in
    rooms.csv order (needed when a paper's sections each start a new room)."""
    for before, after in zip(room_lists, room_lists[1:]):
        if max(position[r["room_id"]] for r in before) > \
                min(position[r["room_id"]] for r in after):
            return False
    return True


def seat_best(papers, rooms, section_of=None, must_split=()):
    """One paper per room, with the best combination of room sizes. Returns
    the RoomPlans in rooms.csv order, or None if this way can't seat them.

    Sections: a paper's sections each start a new room if, for that paper,
    it needs no more rooms than seating it straight on (as before), or if
    the paper is in `must_split` (a teacher of it needs a room without their
    own students). If the rooms then can't keep roll order in rooms.csv
    order, that paper is seated straight on instead and the search runs
    again."""
    sizes, available = room_sizes(rooms)
    if not sizes:
        return None
    position = {room["room_id"]: index for index, room in enumerate(rooms)}
    queues = paper_queues(papers)

    split = set()
    for paper_id, students in queues:
        runs = section_runs(students, section_of)
        if len(runs) < 2:
            continue
        straight = fewest_rooms(len(students), sizes, available)
        by_section = [fewest_rooms(len(run), sizes, available) for run in runs]
        if straight is None or None in by_section:
            continue
        if paper_id in must_split or sum(by_section) <= straight:
            split.add(paper_id)

    while True:
        groups = []                  # (paper_id, students of the group)
        for paper_id, students in queues:
            if paper_id in split:
                groups += [(paper_id, run)
                           for run in section_runs(students, section_of)]
            else:
                groups.append((paper_id, list(students)))

        chosen = best_combination([group for _, group in groups],
                                  sizes, available)
        if chosen is None:
            return None

        # Hand out real rooms: each group takes the first free rooms of each
        # size, in rooms.csv order.
        free = {size: [room for room in rooms if alone_seats(room) == size]
                for size in sizes}
        rooms_of_group = []
        for option in chosen:
            taken = []
            for count, size in zip(option, sizes):
                taken += free[size][:count]
                free[size] = free[size][count:]
            taken.sort(key=lambda room: position[room["room_id"]])
            rooms_of_group.append(taken)

        broken = {paper_id for paper_id in split
                  if not keeps_roll_order(
                      [rooms_of_group[i] for i, (pid, _) in enumerate(groups)
                       if pid == paper_id], position)}
        if not broken:
            break
        split -= broken                   # seat those papers straight on

    plans = []
    for (paper_id, students), taken in zip(groups, rooms_of_group):
        left = list(students)
        for room in taken:
            plans.append(seat_room(room, [[paper_id, left]]))
    plans.sort(key=lambda plan: position[plan.room_id])
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


def seat_best_for_teachers(papers, rooms, section_of, papers_short):
    """seat_best(), but if a teacher of some paper would have no room they
    may sit in (papers_short(plans) names those papers), split that paper by
    section and try again. Returns (plans, papers still short), or
    (None, None) if seat_best() can't seat the slot.

    Why (2026-11-09): with the fewest rooms, a paper's sections often share
    one room. Then a teacher who teaches every section of it has no room
    without their own students. Splitting only those papers fixes it and
    costs the fewest extra rooms."""
    must_split = set()
    while True:
        plans = seat_best(papers, rooms, section_of, must_split)
        if plans is None:
            return None, None
        short = papers_short(plans) if papers_short else set()
        if not short or short <= must_split:
            return plans, short       # done, or nothing more to try
        must_split |= short


def seat_slot(papers, rooms, section_of=None, papers_short=None):
    """Seat one slot. `papers` are the schedule.Paper objects written in it.
    `section_of` is {student_id: section_id} (optional; tests without it get
    no section rule). `papers_short` (optional) is a function: given
    RoomPlans, it returns the IDs of papers with a teacher who has no room
    they may invigilate (see schedule.teacher_room_check()). Returns a list
    of RoomPlans, only for rooms in use, in rooms.csv order. Raises NoPlan
    if the rooms run out even with mixing.

    Tries, in order: the best combination of room sizes (fewest rooms),
    then one paper per room in plain rooms.csv order (the old way), then
    mixing."""
    plans, short = seat_best_for_teachers(papers, rooms, section_of,
                                          papers_short)
    if plans is not None and not short:
        return plans
    old_way = seat_alone(papers, rooms, section_of)
    if old_way is not None:
        # The best way left a teacher without a room (or couldn't seat the
        # slot): the old way may still work. If not, schedule.py reports it.
        return old_way
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


def make_seating(placements, rooms, section_of=None, teacher_check_for=None):
    """Returns {(date, session): [RoomPlan, ...]}, slots in schedule order.
    Raises NoPlan (with the slot named) if any slot cannot be seated.
    `teacher_check_for` (optional): given a slot's papers, returns the
    papers_short function for seat_slot() (see schedule.room_check_for()),
    so the seating here is the same one step 4 checked."""
    papers_of_slot = {}
    for placement in placements:
        slot = (placement.date, placement.session)
        papers_of_slot.setdefault(slot, []).append(placement.paper)

    seating = {}
    for (day, session), papers in papers_of_slot.items():
        try:
            papers_short = (teacher_check_for(papers)
                            if teacher_check_for else None)
            seating[(day, session)] = seat_slot(papers, rooms, section_of,
                                                papers_short)
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

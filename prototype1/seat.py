"""Step 5: give every student a seat (model spec section 9).

This module only SEATS. It takes the placements from schedule.make_schedule()
and the rooms from rooms.csv, and gives back a picture of every room in use
in every slot.

How it works (decided in step 5, 2026-11-03, Krish's idea):

  1. Order.   In each slot, every paper's students are sorted by student_id
              (roll order). All sections of a paper are one queue.
  2. Rooms.   Rooms are opened in rooms.csv order.
  3. Pair.    Two papers share the rooms: at the start, the two with the
              most students (ties by paper ID). A pair stays together room
              after room. Only when one of them is finished does the other
              get a new partner: the paper with the most students still left.
              In each room the paper with more students left takes the odd
              seat columns (1, 3, 5, ...), the other the even ones (2, 4, 6,
              ...). So two neighbouring columns never hold the same paper.
  4. Fill.    Each paper fills its columns front to back, then moves to its
              next column. If a paper runs out, its other seats in that room
              stay EMPTY: a room never holds a third paper.
  5. Alone.   If only one paper is left, it takes the odd columns only, the
              normal one-paper-per-room way.
  6. Repeat.  Next room, until every student has a seat. If the rooms run
              out first, it raises NoPlan and nothing is written.

A room CSV shows the room as the invigilator at the front sees it: row 1 is
the front row, column 1 is on the left.
"""

from dataclasses import dataclass

from schedule import NoPlan


@dataclass
class RoomPlan:
    room_id: str
    papers: list        # paper IDs in this room: one or two
    grid: list          # grid[row][column] = (paper_id, student_id) or None


def update_pair(pair, left):
    """Keep the papers of `pair` that still have students; fill the free
    places with the papers that have the most students left (ties by paper
    ID). Returns the new pair, the paper with more students left first.
    `left` is {paper_id: list of student_ids not yet seated}."""
    pair = [paper_id for paper_id in pair if left[paper_id]]
    waiting = [paper_id for paper_id, students in left.items()
               if students and paper_id not in pair]
    waiting.sort(key=lambda paper_id: (-len(left[paper_id]), paper_id))
    pair = pair + waiting[:2 - len(pair)]
    pair.sort(key=lambda paper_id: (-len(left[paper_id]), paper_id))
    return pair


def fill_columns(grid, columns, paper_id, students):
    """Seat students (in order) down each column, front to back. Removes the
    seated students from the front of `students`."""
    for column in columns:
        for row in grid:
            if not students:
                return
            row[column] = (paper_id, students.pop(0))


def seat_room(room, pair, left):
    """Fill one room with the (one or two) papers of `pair`, the first one in
    the odd columns. Returns a RoomPlan."""
    rows = int(room["rows"])
    columns = int(room["seat_columns"])
    grid = [[None] * columns for _ in range(rows)]

    papers = list(pair)
    odd_columns = list(range(0, columns, 2))     # columns 1, 3, 5 ... on paper
    even_columns = list(range(1, columns, 2))    # columns 2, 4, 6 ...
    fill_columns(grid, odd_columns, papers[0], left[papers[0]])
    if len(papers) == 2:
        fill_columns(grid, even_columns, papers[1], left[papers[1]])
    return RoomPlan(room["room_id"], papers, grid)


def seat_slot(papers, rooms):
    """Seat one slot. `papers` are the schedule.Paper objects written in it.
    Returns a list of RoomPlans, only for rooms in use, in rooms.csv order.
    Raises NoPlan if the rooms run out."""
    left = {paper.paper_id: sorted(paper.students) for paper in papers}
    plans = []
    pair = []
    for room in rooms:
        if not any(left.values()):
            break
        pair = update_pair(pair, left)
        plans.append(seat_room(room, pair, left))

    unseated = {paper_id: len(students)
                for paper_id, students in left.items() if students}
    if unseated:
        total = sum(len(paper.students) for paper in papers)
        names = ", ".join(f"{paper_id} ({count})"
                          for paper_id, count in sorted(unseated.items()))
        raise NoPlan(
            "No plan possible.\n"
            "Rule: seats\n"
            f"All {len(rooms)} rooms are full, two papers per room, but "
            f"{sum(unseated.values())} of {total} students still have no "
            f"seat: {names}.")
    return plans


def make_seating(placements, rooms):
    """Returns {(date, session): [RoomPlan, ...]}, slots in schedule order.
    Raises NoPlan (with the slot named) if any slot cannot be seated."""
    papers_of_slot = {}
    for placement in placements:
        slot = (placement.date, placement.session)
        papers_of_slot.setdefault(slot, []).append(placement.paper)

    seating = {}
    for (day, session), papers in papers_of_slot.items():
        try:
            seating[(day, session)] = seat_slot(papers, rooms)
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

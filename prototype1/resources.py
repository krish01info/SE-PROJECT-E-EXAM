"""Find legal seating and invigilators for one slot, without writing candidates."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterator


@dataclass
class RoomPlan:
    room_id: str
    seats: list[list[tuple[str, str] | None]]
    teachers: list[str]


@dataclass
class SlotPlan:
    rooms: list[RoomPlan]
    exemptions: list[tuple[str, str]]  # (teacher_id, paper_id)


class ResourceError(Exception):
    """No legal seating/staffing arrangement exists for this set of papers."""


def _column_order(counts: tuple[int, ...], columns: int) -> list[int | None] | None:
    """Arrange paper columns, inserting empty columns as separators if needed."""
    remaining = list(counts)

    def place(previous: int | None, left: int) -> list[int | None] | None:
        if not any(remaining):
            return [None] * left
        if sum(remaining) > left or max(remaining) > (left + 1) // 2:
            return None
        # Most numerous first avoids dead ends; paper order breaks ties.
        for paper in sorted(range(len(counts)), key=lambda p: (-remaining[p], p)):
            if remaining[paper] == 0 or paper == previous:
                continue
            remaining[paper] -= 1
            tail = place(paper, left - 1)
            remaining[paper] += 1
            if tail is not None:
                return [paper] + tail
        if left > sum(remaining):
            tail = place(None, left - 1)
            if tail is not None:
                return [None] + tail
        return None

    return place(None, columns)


class SlotPlanner:
    def __init__(
        self,
        papers: list[dict[str, Any]],
        rooms: list[dict[str, Any]],
        teachers: list[dict[str, str]],
        teaching: list[dict[str, str]],
        registrations: list[dict[str, str]],
        student_sections: dict[str, str],
        invigilators_per_room: int,
    ) -> None:
        self.rooms = rooms
        self.teachers = [row["teacher_id"].strip() for row in teachers]
        ranks = {row["teacher_id"].strip(): row["rank"].strip() for row in teachers}
        self.per_room = invigilators_per_room
        self.own_students: dict[tuple[str, str], set[str]] = {}
        self.required: dict[str, set[str]] = {}
        self.exemptions: list[tuple[str, str]] = []

        code_to_paper = {
            code: paper["paper_id"] for paper in papers for code in paper["course_codes"]
        }
        students_by_class: dict[tuple[str, str], set[str]] = {}
        for row in registrations:
            student = row["student_id"].strip()
            key = (row["course_code"].strip(), student_sections[student])
            students_by_class.setdefault(key, set()).add(student)
        for row in teaching:
            teacher = row["teacher_id"].strip()
            code = row["course_code"].strip()
            key = (code_to_paper[code], teacher)
            self.own_students.setdefault(key, set()).update(
                students_by_class.get((code, row["section_id"].strip()), set())
            )
        for paper in papers:
            paper_id = paper["paper_id"]
            for teacher in self.teachers:
                own = self.own_students.get((paper_id, teacher), set())
                if not own or ranks[teacher] == "PHD":
                    continue
                if own == set(paper["students"]):
                    self.exemptions.append((teacher, paper_id))
                else:
                    self.required.setdefault(teacher, set()).add(paper_id)

    def check_bounds(self, papers: list[dict[str, Any]]) -> None:
        """Necessary bounds only: adding another paper may enable room mixing."""
        sizes = [len(paper["students"]) for paper in papers]
        physical = sum(int(r["rows"]) * int(r["seat_columns"]) for r in self.rooms)
        single_paper = sum(
            int(r["rows"]) * ((int(r["seat_columns"]) + 1) // 2) for r in self.rooms
        )
        for paper, size in zip(papers, sizes):
            if size > single_paper:
                raise ResourceError(
                    f"Rule: seats. Paper {paper['paper_id']} needs {size} seats; "
                    f"the column rule allows at most {single_paper} across all rooms."
                )
        if sum(sizes) > physical:
            raise ResourceError(
                f"Rule: seats. Slot needs {sum(sizes)} seats; rooms give {physical}."
            )
        # Even fully mixed rooms cannot exceed these staffable prefix capacities.
        available_rooms = len(self.teachers) // self.per_room
        staffable = sum(
            int(r["rows"]) * int(r["seat_columns"])
            for r in self.rooms[:available_rooms]
        )
        if sum(sizes) > staffable:
            raise ResourceError(
                f"Rule: invigilators. {len(self.teachers)} teachers can staff at most "
                f"{available_rooms} rooms at {self.per_room} per room; those rooms hold "
                f"at most {staffable} of the slot's {sum(sizes)} students."
            )

    def _single_paper_rooms_fit(self, sizes: tuple[int, ...]) -> bool:
        # This is a seating-only check: a staffing shortage does not itself
        # permit mixing under the current spec. Filling a dedicated room as
        # much as possible is sufficient here; actual chunk sizes are searched
        # separately because those sizes affect teacher eligibility.
        @lru_cache(maxsize=None)
        def place(index: int, remaining: tuple[int, ...]) -> bool:
            if not any(remaining):
                return True
            if index == len(self.rooms):
                return False
            room = self.rooms[index]
            capacity = int(room["rows"]) * ((int(room["seat_columns"]) + 1) // 2)
            for paper, size in enumerate(remaining):
                if size:
                    next_sizes = list(remaining)
                    next_sizes[paper] = max(0, size - capacity)
                    if place(index + 1, tuple(next_sizes)):
                        return True
            return False

        return place(0, sizes)

    def _allocations(
        self, remaining: tuple[int, ...], room: dict[str, Any], mixed: bool,
    ) -> Iterator[tuple[tuple[int, ...], list[int | None]]]:
        rows, columns = int(room["rows"]), int(room["seat_columns"])
        amounts = [0] * len(remaining)

        def choose(paper: int, columns_used: int) -> Iterator:
            if paper == len(remaining):
                if not any(amounts):
                    return
                counts = tuple((amount + rows - 1) // rows for amount in amounts)
                order = _column_order(counts, columns)
                if order is not None:
                    yield tuple(amounts), order
                return
            limit = min(remaining[paper], ((columns + 1) // 2) * rows)
            if not mixed and any(amounts[:paper]):
                limit = 0
            limit = min(limit, (columns - columns_used) * rows)
            for amount in range(limit, -1, -1):
                amounts[paper] = amount
                used = (amount + rows - 1) // rows
                yield from choose(paper + 1, columns_used + used)
            amounts[paper] = 0

        yield from choose(0, 0)

    def _seat_room(
        self, papers: list[dict], remaining: tuple[int, ...], room: dict,
        amounts: tuple[int, ...], columns: list[int | None],
    ) -> RoomPlan:
        rows = int(room["rows"])
        seats: list[list[tuple[str, str] | None]] = [[None] * len(columns) for _ in range(rows)]
        taken = [0] * len(papers)
        for column, paper in enumerate(columns):
            if paper is None:
                continue
            start = len(papers[paper]["students"]) - remaining[paper] + taken[paper]
            count = min(rows, amounts[paper] - taken[paper])
            for row in range(count):
                seats[row][column] = (
                    papers[paper]["paper_id"], papers[paper]["students"][start + row],
                )
            taken[paper] += count
        return RoomPlan(room["room_id"].strip(), seats, [])

    def _assign_teachers(
        self, rooms: list[RoomPlan], paper_ids: set[str], loads: dict[str, int],
        complete: bool,
    ) -> list[list[str]] | None:
        contents = [{cell for row in room.seats for cell in row if cell} for room in rooms]
        room_papers = [{paper for paper, _ in cells} for cells in contents]
        required = {
            teacher: papers & paper_ids for teacher, papers in self.required.items()
            if papers & paper_ids
        } if complete else {}
        edges: dict[str, list[int]] = {}
        for teacher in self.teachers:
            edges[teacher] = [
                index for index, cells in enumerate(contents)
                if required.get(teacher, set()) <= room_papers[index]
                and not any(
                    student in self.own_students.get((paper, teacher), set())
                    for paper, student in cells
                )
            ]
        # Match mandatory teachers first. Augmenting paths can move an existing
        # teacher to another room, but never remove a mandatory teacher.
        duties: list[str | None] = [None] * (len(rooms) * self.per_room)

        def match(teacher: str, seen: set[int]) -> bool:
            for room in edges[teacher]:
                for duty in range(room * self.per_room, (room + 1) * self.per_room):
                    if duty in seen:
                        continue
                    seen.add(duty)
                    occupant = duties[duty]
                    if occupant is None or match(occupant, seen):
                        duties[duty] = teacher
                        return True
            return False

        for teacher in sorted(required, key=lambda t: (len(edges[t]), self.teachers.index(t))):
            if not match(teacher, set()):
                return None
        for teacher in sorted(self.teachers, key=lambda t: (loads.get(t, 0), self.teachers.index(t))):
            if teacher not in required and None in duties:
                match(teacher, set())
        if None in duties:
            return None
        return [
            sorted(duties[i:i + self.per_room], key=self.teachers.index)
            for i in range(0, len(duties), self.per_room)
        ]

    def plan(self, papers: list[dict[str, Any]], loads: dict[str, int] | None = None) -> SlotPlan:
        self.check_bounds(papers)
        sizes = tuple(len(paper["students"]) for paper in papers)
        mixed = not self._single_paper_rooms_fit(sizes)
        paper_ids = {paper["paper_id"] for paper in papers}
        rooms: list[RoomPlan] = []
        seating_found = False

        def place(index: int, remaining: tuple[int, ...]) -> list[RoomPlan] | None:
            nonlocal seating_found
            if not any(remaining):
                seating_found = True
                teachers = self._assign_teachers(rooms, paper_ids, loads or {}, complete=True)
                if teachers is None:
                    return None  # Keep searching other seating layouts internally.
                return [
                    RoomPlan(room.room_id, room.seats, assigned)
                    for room, assigned in zip(rooms, teachers)
                ]
            if index == len(self.rooms):
                return None
            future = self.rooms[index:]
            if sum(remaining) > sum(
                int(r["rows"]) * (int(r["seat_columns"]) if mixed else (int(r["seat_columns"]) + 1) // 2)
                for r in future
            ):
                return None
            per_paper = sum(int(r["rows"]) * ((int(r["seat_columns"]) + 1) // 2) for r in future)
            if any(size > per_paper for size in remaining):
                return None
            for amounts, columns in self._allocations(remaining, self.rooms[index], mixed):
                next_sizes = tuple(size - amount for size, amount in zip(remaining, amounts))
                rooms.append(self._seat_room(papers, remaining, self.rooms[index], amounts, columns))
                # A filled room's students never change deeper in this search.
                # If these rooms alone cannot be staffed, adding rooms cannot help.
                if self._assign_teachers(rooms, paper_ids, {}, complete=False) is not None:
                    result = place(index + 1, next_sizes)
                    if result is not None:
                        return result
                rooms.pop()
            return None

        result = place(0, sizes)
        if result is None:
            rule = "eligible invigilators" if seating_found else "seating or eligible invigilators"
            raise ResourceError(
                f"Rule: {rule}. Papers {', '.join(p['paper_id'] for p in papers)} "
                f"need {sum(sizes)} seats and {self.per_room} teachers per open room. "
                f"No legal arrangement using {len(self.rooms)} rooms and "
                f"{len(self.teachers)} teachers satisfies the column, own-class and own-paper rules."
            )
        return SlotPlan(result, [pair for pair in self.exemptions if pair[1] in paper_ids])

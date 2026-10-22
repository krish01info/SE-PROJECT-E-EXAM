from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from resources import ResourceError, SlotPlan, SlotPlanner


@dataclass
class ExamPlan:
    schedule: list[dict[str, Any]]
    slots: dict[tuple[date, str], SlotPlan]


class NoScheduleError(Exception):
    """Raised when no paper placement satisfies the scheduling rules."""


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _paper_data(
    courses: list[dict[str, Any]],
    registrations: list[dict[str, Any]],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    codes = [str(row["course_code"]).strip() for row in courses]
    groups = constraints.get("same_paper", [])
    code_to_paper = {code: code for code in codes}
    group_codes: dict[str, list[str]] = {}

    for group in groups:
        group = [str(code).strip() for code in group]
        paper_id = group[0]
        group_codes[paper_id] = group
        for code in group:
            code_to_paper[code] = paper_id

    paper_order: list[str] = []
    for code in codes:
        paper_id = code_to_paper[code]
        if paper_id not in paper_order:
            paper_order.append(paper_id)

    paper_students: dict[str, set[str]] = {paper_id: set() for paper_id in paper_order}
    for row in registrations:
        course_code = str(row["course_code"]).strip()
        student_id = str(row["student_id"]).strip()
        paper_students[code_to_paper[course_code]].add(student_id)

    return [
        {
            "paper_id": paper_id,
            "course_codes": group_codes.get(
                paper_id,
                [code for code in codes if code_to_paper[code] == paper_id],
            ),
            "students": sorted(paper_students[paper_id]),
        }
        for paper_id in paper_order
    ]


def _exam_dates(settings: dict[str, Any]) -> list[date]:
    start = _as_date(settings["start_date"])
    end = _as_date(settings["end_date"])
    weekdays = set(settings["exam_weekdays"])
    holidays = {_as_date(value) for value in settings.get("holidays", [])}
    dates: list[date] = []
    day = start
    while day <= end:
        if day.strftime("%a") in weekdays and day not in holidays:
            dates.append(day)
        day += timedelta(days=1)
    return dates


def schedule_papers(
    courses: list[dict[str, Any]],
    registrations: list[dict[str, Any]],
    settings: dict[str, Any],
    constraints: dict[str, Any],
    *,
    rooms: list[dict[str, Any]],
    teachers: list[dict[str, str]],
    teaching: list[dict[str, str]],
    student_sections: dict[str, str],
) -> ExamPlan:
    """Backtrack until dates, legal seating and eligible duties all fit."""
    papers = _paper_data(courses, registrations, constraints)
    dates = _exam_dates(settings)
    sessions = list(settings["sessions"])
    min_gap_days = int(settings["min_gap_days"])

    if not dates:
        raise NoScheduleError("No plan possible. Rule: exam dates. No usable dates are available in the configured window.")

    planner = SlotPlanner(
        papers, rooms, teachers, teaching, registrations, student_sections,
        int(settings["invigilators_per_room"]),
    )
    for paper in papers:
        try:
            planner.check_bounds([paper])
        except ResourceError as exc:
            raise NoScheduleError(f"No plan possible. {exc}") from exc

    # The earliest available date always leaves the most space for later exams.
    spaced_dates: list[date] = []
    for exam_date in dates:
        if not spaced_dates or (exam_date - spaced_dates[-1]).days >= min_gap_days:
            spaced_dates.append(exam_date)
    student_papers: dict[str, int] = {}
    for paper in papers:
        for student in paper["students"]:
            student_papers[student] = student_papers.get(student, 0) + 1
    for student, count in student_papers.items():
        if count > len(spaced_dates):
            raise NoScheduleError(
                f"No plan possible. Rule: student exam gap. Student {student} has "
                f"{count} papers; the window allows at most {len(spaced_dates)} "
                f"exam dates with min_gap_days={min_gap_days}."
            )

    assignment: dict[str, tuple[date, str]] = {}
    slot_papers: dict[tuple[date, str], list[dict[str, Any]]] = {}
    slot_plans: dict[tuple[date, str], SlotPlan] = {}
    resource_cache: dict[tuple, SlotPlan | str] = {}
    last_resource_error: str | None = None

    def finish_slots() -> bool:
        nonlocal last_resource_error
        slot_plans.clear()
        loads: dict[str, int] = {}
        for slot in sorted(slot_papers, key=lambda s: (s[0], sessions.index(s[1]))):
            if not slot_papers[slot]:
                continue
            key = (
                tuple(p["paper_id"] for p in slot_papers[slot]),
                tuple(loads.get(t, 0) for t in planner.teachers),
            )
            if key not in resource_cache:
                try:
                    resource_cache[key] = planner.plan(slot_papers[slot], loads)
                except ResourceError as exc:
                    resource_cache[key] = str(exc)
            result = resource_cache[key]
            if isinstance(result, str):
                last_resource_error = f"Rejected slot {slot[0].isoformat()} {slot[1]}: {result}"
                return False
            slot_plans[slot] = result
            for room in result.rooms:
                for teacher in room.teachers:
                    loads[teacher] = loads.get(teacher, 0) + 1
        return True

    def fits(paper: dict[str, Any], exam_date: date) -> bool:
        students = set(paper["students"])
        for other in papers:
            other_assignment = assignment.get(other["paper_id"])
            if other_assignment is None:
                continue
            if students.intersection(other["students"]):
                if abs((exam_date - other_assignment[0]).days) < min_gap_days:
                    return False
        return True

    def place(index: int) -> bool:
        nonlocal last_resource_error
        if index == len(papers):
            return finish_slots()
        paper = papers[index]
        for exam_date in dates:
            if not fits(paper, exam_date):
                continue
            for session in sessions:
                slot = (exam_date, session)
                placed = slot_papers.setdefault(slot, [])
                placed.append(paper)
                assignment[paper["paper_id"]] = slot
                try:
                    # Full staffing checks wait until the slot's papers are known:
                    # another paper can enable mixing and reduce the room count.
                    planner.check_bounds(placed)
                except ResourceError as exc:
                    last_resource_error = f"Rejected slot {exam_date.isoformat()} {session}: {exc}"
                else:
                    if place(index + 1):
                        return True
                placed.pop()
                del assignment[paper["paper_id"]]
        return False

    if not place(0):
        if last_resource_error:
            raise NoScheduleError(
                "No plan possible. No complete schedule satisfies the student gap, "
                f"seating and duty rules.\n{last_resource_error}"
            )
        raise NoScheduleError(
            "No plan possible. Rule: student exam gap. "
            f"Could not place all papers within the configured window with min_gap_days={min_gap_days}."
        )

    schedule = [
        {
            "date": assignment[paper["paper_id"]][0],
            "session": assignment[paper["paper_id"]][1],
            "paper_id": paper["paper_id"],
            "course_codes": paper["course_codes"],
            "students": paper["students"],
        }
        for paper in papers
    ]
    return ExamPlan(schedule, slot_plans)

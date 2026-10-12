"""Core entities, mirroring the relational CSV tables (SRS 3.4).

Only identifiers are stored for people; names are never part of the schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .config import Config


@dataclass(frozen=True)
class Section:
    section_id: str
    cohort_id: str


@dataclass(frozen=True)
class Student:
    student_id: str  # roll number; roll order == sort order of this string
    section_id: str


@dataclass(frozen=True)
class Teacher:
    teacher_id: str
    rank: str  # professor | associate | assistant | phd
    department: str


@dataclass(frozen=True)
class Paper:
    paper_id: str
    title: str
    department: str


@dataclass(frozen=True)
class CourseCode:
    course_code: str
    paper_id: str
    cohort_id: str


@dataclass(frozen=True)
class Room:
    room_id: str
    building: str
    bench_cols: int  # number of bench columns (aisles between them)
    rows: int  # benches per column, front to back
    seats_per_bench: int  # 1 (2-wide bench) or 2 (3-wide bench)
    priority: int  # lower opens first

    @property
    def capacity(self) -> int:
        return self.bench_cols * self.rows * self.seats_per_bench


@dataclass(frozen=True)
class Slot:
    day_index: int  # index into the exam-day calendar
    date: date
    session_index: int
    session: str

    @property
    def key(self) -> str:
        return f"{self.date.isoformat()}_{self.session}"

    @property
    def label(self) -> str:
        return f"{self.date.strftime('%a %d %b %Y')} — {self.session}"

    def __lt__(self, other: "Slot") -> bool:
        return (self.day_index, self.session_index) < (other.day_index, other.session_index)


@dataclass(frozen=True)
class Pin:
    """A manual override (C9). kind = 'paper_slot' or 'teacher_room'."""

    kind: str
    paper_id: str = ""
    teacher_id: str = ""
    room_id: str = ""
    date: str = ""
    session: str = ""

    def describe(self) -> str:
        if self.kind == "paper_slot":
            return f"pin paper {self.paper_id} to {self.date} {self.session}"
        return f"pin teacher {self.teacher_id} to room {self.room_id} on {self.date} {self.session}"


@dataclass
class Dataset:
    config: Config
    sections: dict[str, Section] = field(default_factory=dict)
    students: dict[str, Student] = field(default_factory=dict)
    teachers: dict[str, Teacher] = field(default_factory=dict)
    papers: dict[str, Paper] = field(default_factory=dict)
    course_codes: dict[str, CourseCode] = field(default_factory=dict)
    registrations: list[tuple[str, str]] = field(default_factory=list)  # (student, code)
    teaching: list[tuple[str, str, str]] = field(default_factory=list)  # (teacher, code, section)
    rooms: list[Room] = field(default_factory=list)  # sorted by priority
    pins: list[Pin] = field(default_factory=list)
    issues: list = field(default_factory=list)  # validation warnings kept for reports

    def slots(self) -> list[Slot]:
        out = []
        for di, d in enumerate(self.config.exam_days()):
            for si, s in enumerate(self.config.sessions):
                out.append(Slot(di, d, si, s))
        return out

    def cohort_of(self, student_id: str) -> str:
        return self.sections[self.students[student_id].section_id].cohort_id

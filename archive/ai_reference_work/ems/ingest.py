"""M1 — Data Ingestion & Validation (C1, MoSCoW R2).

Reads every input table, checks format and referential integrity, and either
returns a validated :class:`Dataset` or raises :class:`ValidationError` whose
report names the exact file, row and rule that failed.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import RANKS, Config
from .model import CourseCode, Dataset, Paper, Pin, Room, Section, Student, Teacher

SCHEMA: dict[str, list[str]] = {
    "sections.csv": ["section_id", "cohort_id"],
    "teachers.csv": ["teacher_id", "rank", "department"],
    "papers.csv": ["paper_id", "title", "department"],
    "course_codes.csv": ["course_code", "paper_id", "cohort_id"],
    "registrations.csv": ["student_id", "course_code"],
    "teaching.csv": ["teacher_id", "course_code", "section_id"],
    "rooms.csv": ["room_id", "building", "bench_cols", "rows", "seats_per_bench", "priority"],
}
STUDENT_SCHEMA = ["student_id"]
PIN_SCHEMA = ["kind", "paper_id", "teacher_id", "room_id", "date", "session"]


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning"
    file: str
    row: int  # 1-based data row (header = row 0); 0 = whole file
    rule: str
    message: str

    def __str__(self) -> str:
        where = f"{self.file}" + (f", row {self.row}" if self.row else "")
        return f"[{self.severity.upper()}] {where} — {self.rule}: {self.message}"


class ValidationError(Exception):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        errors = [i for i in issues if i.severity == "error"]
        super().__init__(f"{len(errors)} validation error(s)")

    def report(self) -> str:
        return format_issues(self.issues)


def format_issues(issues: list[Issue]) -> str:
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    lines = [f"Validation: {len(errors)} error(s), {len(warnings)} warning(s)"]
    lines += [f"  {i}" for i in errors + warnings]
    return "\n".join(lines)


class _Reader:
    def __init__(self, root: Path):
        self.root = root
        self.issues: list[Issue] = []

    def err(self, file, row, rule, msg):
        self.issues.append(Issue("error", file, row, rule, msg))

    def warn(self, file, row, rule, msg):
        self.issues.append(Issue("warning", file, row, rule, msg))

    def rows(self, rel: str, columns: list[str], optional: bool = False):
        path = self.root / rel
        if not path.exists():
            if not optional:
                self.err(rel, 0, "missing-file", f"required file {rel} not found")
            return []
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = [h.strip() for h in (reader.fieldnames or [])]
            missing = [c for c in columns if c not in header]
            if missing:
                self.err(rel, 0, "missing-columns", f"missing column(s): {', '.join(missing)}")
                return []
            out = []
            for n, raw in enumerate(reader, start=1):
                row = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
                if not any(row.values()):
                    continue  # tolerate blank lines
                out.append((n, row))
            return out


def _int(reader: _Reader, file, n, row, col, low=1, allowed=None):
    try:
        v = int(row[col])
    except ValueError:
        reader.err(file, n, "not-an-integer", f"{col}={row[col]!r} is not an integer")
        return None
    if allowed is not None and v not in allowed:
        reader.err(file, n, "out-of-range", f"{col}={v} must be one of {sorted(allowed)}")
        return None
    if v < low:
        reader.err(file, n, "out-of-range", f"{col}={v} must be >= {low}")
        return None
    return v


def load_dataset(path: str | Path, pins_file: str | Path | None = None, strict: bool = True) -> Dataset:
    """Load and validate a dataset directory. Raises ValidationError on any error."""
    root = Path(path)
    config = Config.load(root)
    ds = Dataset(config=config)
    r = _Reader(root)
    sid_re = re.compile(config["validation"]["student_id_pattern"])
    tid_re = re.compile(config["validation"]["teacher_id_pattern"])

    def required(file, n, row, cols):
        ok = True
        for c in cols:
            if not row.get(c):
                r.err(file, n, "empty-field", f"{c} is empty")
                ok = False
        return ok

    # --- sections -------------------------------------------------------
    for n, row in r.rows("sections.csv", SCHEMA["sections.csv"]):
        if not required("sections.csv", n, row, SCHEMA["sections.csv"]):
            continue
        if row["section_id"] in ds.sections:
            r.err("sections.csv", n, "duplicate-key", f"section {row['section_id']} listed twice")
            continue
        ds.sections[row["section_id"]] = Section(row["section_id"], row["cohort_id"])

    # --- students: one CSV per section ------------------------------------
    student_dir = root / "students"
    if not student_dir.is_dir():
        r.err("students/", 0, "missing-file", "students/ directory (one CSV per section) not found")
    else:
        files = sorted(student_dir.glob("*.csv"))
        seen_files = set()
        for f in files:
            sec = f.stem
            seen_files.add(sec)
            rel = f"students/{f.name}"
            if sec not in ds.sections:
                r.err(rel, 0, "unknown-section", f"roster file for section {sec!r} not in sections.csv")
                continue
            for n, row in r.rows(rel, STUDENT_SCHEMA):
                sid = row["student_id"]
                if not sid_re.match(sid):
                    r.err(rel, n, "bad-id-format", f"student_id {sid!r} does not match {sid_re.pattern}")
                    continue
                if sid in ds.students:
                    prev = ds.students[sid].section_id
                    r.err(rel, n, "student-in-two-sections", f"{sid} already in section {prev}")
                    continue
                ds.students[sid] = Student(sid, sec)
        for sec in ds.sections:
            if sec not in seen_files:
                r.warn("sections.csv", 0, "empty-section", f"section {sec} has no roster file")

    # --- teachers ---------------------------------------------------------
    for n, row in r.rows("teachers.csv", SCHEMA["teachers.csv"]):
        if not required("teachers.csv", n, row, ["teacher_id", "rank"]):
            continue
        tid, rank = row["teacher_id"], row["rank"].lower()
        if not tid_re.match(tid):
            r.err("teachers.csv", n, "bad-id-format", f"teacher_id {tid!r} does not match {tid_re.pattern}")
            continue
        if rank not in RANKS:
            r.err("teachers.csv", n, "bad-rank", f"rank {row['rank']!r} must be one of {', '.join(RANKS)}")
            continue
        if tid in ds.teachers:
            r.err("teachers.csv", n, "duplicate-key", f"teacher {tid} listed twice")
            continue
        ds.teachers[tid] = Teacher(tid, rank, row.get("department", ""))

    # --- papers & course codes (C2 inputs) --------------------------------
    for n, row in r.rows("papers.csv", SCHEMA["papers.csv"]):
        if not required("papers.csv", n, row, ["paper_id", "title"]):
            continue
        if row["paper_id"] in ds.papers:
            r.err("papers.csv", n, "duplicate-key", f"paper {row['paper_id']} listed twice")
            continue
        ds.papers[row["paper_id"]] = Paper(row["paper_id"], row["title"], row.get("department", ""))

    cohorts = {s.cohort_id for s in ds.sections.values()}
    for n, row in r.rows("course_codes.csv", SCHEMA["course_codes.csv"]):
        if not required("course_codes.csv", n, row, SCHEMA["course_codes.csv"]):
            continue
        code = row["course_code"]
        if code in ds.course_codes:
            r.err("course_codes.csv", n, "duplicate-key", f"course code {code} mapped twice")
            continue
        if row["paper_id"] not in ds.papers:
            r.err("course_codes.csv", n, "unmapped-code", f"{code} maps to unknown paper {row['paper_id']}")
            continue
        if row["cohort_id"] not in cohorts:
            r.err("course_codes.csv", n, "unknown-cohort", f"{code} offered to unknown cohort {row['cohort_id']}")
            continue
        ds.course_codes[code] = CourseCode(code, row["paper_id"], row["cohort_id"])

    mapped = {c.paper_id for c in ds.course_codes.values()}
    for pid in ds.papers:
        if pid not in mapped:
            r.warn("papers.csv", 0, "paper-without-code", f"paper {pid} has no course code; it will not be examined")

    # --- registrations ----------------------------------------------------
    seen_reg = set()
    for n, row in r.rows("registrations.csv", SCHEMA["registrations.csv"]):
        if not required("registrations.csv", n, row, SCHEMA["registrations.csv"]):
            continue
        sid, code = row["student_id"], row["course_code"]
        if sid not in ds.students:
            r.err("registrations.csv", n, "unknown-student", f"student {sid} is not on any section roster")
            continue
        if code not in ds.course_codes:
            r.err("registrations.csv", n, "unknown-course-code", f"course code {code} not in course_codes.csv")
            continue
        if (sid, code) in seen_reg:
            r.warn("registrations.csv", n, "duplicate-registration", f"{sid} registered for {code} twice (kept once)")
            continue
        seen_reg.add((sid, code))
        ds.registrations.append((sid, code))
    registered = {s for s, _ in ds.registrations}
    unreg = [s for s in ds.students if s not in registered]
    if unreg:
        r.warn("registrations.csv", 0, "student-without-registration",
               f"{len(unreg)} student(s) have no registrations, e.g. {', '.join(sorted(unreg)[:5])}")

    # --- teaching assignments ---------------------------------------------
    seen_teach = set()
    for n, row in r.rows("teaching.csv", SCHEMA["teaching.csv"]):
        if not required("teaching.csv", n, row, SCHEMA["teaching.csv"]):
            continue
        tid, code, sec = row["teacher_id"], row["course_code"], row["section_id"]
        if tid not in ds.teachers:
            r.err("teaching.csv", n, "unknown-teacher", f"teacher {tid} not in teachers.csv")
            continue
        if code not in ds.course_codes:
            r.err("teaching.csv", n, "unknown-course-code", f"course code {code} not in course_codes.csv")
            continue
        if sec not in ds.sections:
            r.err("teaching.csv", n, "unknown-section", f"section {sec} not in sections.csv")
            continue
        if ds.sections[sec].cohort_id != ds.course_codes[code].cohort_id:
            r.err("teaching.csv", n, "cohort-mismatch",
                  f"{code} is offered to {ds.course_codes[code].cohort_id} but section {sec} "
                  f"belongs to {ds.sections[sec].cohort_id}")
            continue
        if (tid, code, sec) in seen_teach:
            continue
        seen_teach.add((tid, code, sec))
        ds.teaching.append((tid, code, sec))

    # --- rooms -------------------------------------------------------------
    rooms = []
    for n, row in r.rows("rooms.csv", SCHEMA["rooms.csv"]):
        if not required("rooms.csv", n, row, SCHEMA["rooms.csv"]):
            continue
        vals = [
            _int(r, "rooms.csv", n, row, "bench_cols"),
            _int(r, "rooms.csv", n, row, "rows"),
            _int(r, "rooms.csv", n, row, "seats_per_bench", allowed={1, 2}),
            _int(r, "rooms.csv", n, row, "priority", low=0),
        ]
        if None in vals:
            continue
        if any(x.room_id == row["room_id"] for x in rooms):
            r.err("rooms.csv", n, "duplicate-key", f"room {row['room_id']} listed twice")
            continue
        rooms.append(Room(row["room_id"], row["building"], *vals))
    ds.rooms = sorted(rooms, key=lambda x: (x.priority, x.room_id))

    # --- pins (D7, optional) ---------------------------------------------
    pin_path = Path(pins_file) if pins_file else root / "pins.csv"
    if pin_path.exists():
        prev_root = r.root
        r.root = pin_path.parent
        days = {d.isoformat() for d in config.exam_days()}
        room_ids = {x.room_id for x in ds.rooms}
        for n, row in r.rows(pin_path.name, PIN_SCHEMA):
            f = pin_path.name
            kind = row["kind"]
            if kind not in ("paper_slot", "teacher_room"):
                r.err(f, n, "bad-pin-kind", f"kind {kind!r} must be paper_slot or teacher_room")
                continue
            if row["date"] not in days:
                r.err(f, n, "pin-date-outside-calendar", f"date {row['date']} is not an exam day")
                continue
            if row["session"] not in config.sessions:
                r.err(f, n, "bad-session", f"session {row['session']!r} not in {config.sessions}")
                continue
            if kind == "paper_slot" and row["paper_id"] not in ds.papers:
                r.err(f, n, "unknown-paper", f"paper {row['paper_id']} not in papers.csv")
                continue
            if kind == "teacher_room":
                if row["teacher_id"] not in ds.teachers:
                    r.err(f, n, "unknown-teacher", f"teacher {row['teacher_id']} not in teachers.csv")
                    continue
                if row["room_id"] not in room_ids:
                    r.err(f, n, "unknown-room", f"room {row['room_id']} not in rooms.csv")
                    continue
            ds.pins.append(Pin(kind, row["paper_id"], row["teacher_id"], row["room_id"], row["date"], row["session"]))
        r.root = prev_root

    if not ds.config.exam_days():
        r.err("config.json", 0, "empty-calendar", "the calendar contains no exam days")

    ds.issues = r.issues
    if strict and any(i.severity == "error" for i in r.issues):
        raise ValidationError(r.issues)
    return ds


def parse_date(s: str) -> date:
    return date.fromisoformat(s)

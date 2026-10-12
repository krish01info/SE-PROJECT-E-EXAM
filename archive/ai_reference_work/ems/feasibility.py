"""M7 — Feasibility & Diagnostics (C7 pre-solve check, C8 diagnosis types).

The pre-solve check compares demand with capacity using bounds that are
cheap to compute and *provably necessary*, so a dataset that can never be
solved is rejected in milliseconds with the exact deficit (MoSCoW R8).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .config import INVIGILATION_ONLY
from .conflicts import ConflictGraph
from .geometry import RoomLayout
from .mapping import PaperMap
from .model import Dataset


@dataclass
class Finding:
    severity: str  # "blocking" | "warning" | "info"
    code: str
    message: str
    entities: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        tag = {"blocking": "BLOCKING", "warning": "WARNING", "info": "info"}[self.severity]
        return f"[{tag}] {self.code}: {self.message}"


@dataclass
class Diagnosis:
    """C8 — why a stage failed, in terms staff can act on."""

    stage: str  # scheduling | seating | duties
    summary: str
    findings: list[Finding] = field(default_factory=list)

    def text(self) -> str:
        lines = [f"Infeasible at stage: {self.stage}", self.summary]
        lines += [f"  - {f}" for f in self.findings]
        return "\n".join(lines)


@dataclass
class SlotCapacity:
    rooms_usable: int  # min(rooms, invigilators // per_room)
    limited_by: str  # "rooms" | "invigilators"
    cap_a: int  # seats on side A across usable rooms (largest single paper)
    cap_b: int
    layouts: list[RoomLayout]

    @property
    def total(self) -> int:
        return self.cap_a + self.cap_b


def slot_capacity(ds: Dataset, layouts: list[RoomLayout]) -> SlotCapacity:
    per_room = int(ds.config["duties"]["invigilators_per_room"])
    by_staff = len(ds.teachers) // per_room if per_room else len(layouts)
    k = min(len(layouts), by_staff)
    usable = layouts[:k]
    return SlotCapacity(
        rooms_usable=k,
        limited_by="invigilators" if by_staff < len(layouts) else "rooms",
        cap_a=sum(len(l.side_a) for l in usable),
        cap_b=sum(len(l.side_b) for l in usable),
        layouts=usable,
    )


@dataclass
class FeasibilityReport:
    findings: list[Finding]
    capacity: SlotCapacity
    min_days_needed: int
    days_available: int

    @property
    def ok(self) -> bool:
        return not any(f.severity == "blocking" for f in self.findings)

    def text(self) -> str:
        head = "PASS — no capacity shortfall detected" if self.ok else "FAIL — capacity shortfall"
        lines = [f"Pre-solve feasibility check: {head}"]
        lines += [f"  {f}" for f in self.findings]
        return "\n".join(lines)


def required_days(n_papers: int, gap: int) -> int:
    return 0 if n_papers == 0 else (n_papers - 1) * gap + 1


def coverage_exempt(ds: Dataset, pm: PaperMap, cg: ConflictGraph) -> dict[str, str]:
    """Teachers for whom 'one duty on a paper you teach' is impossible.

    A teacher can only invigilate paper p in a room with no student of a
    section they taught for p. If they taught *every* section writing every
    paper they teach, no such room can exist.
    """
    exempt = {}
    sections_writing: dict[str, set[str]] = {}
    for p, studs in pm.paper_students.items():
        sections_writing[p] = {ds.students[s].section_id for s in studs}
    for tid, papers in cg.teacher_papers.items():
        t = ds.teachers[tid]
        if t.rank in INVIGILATION_ONLY:
            continue
        possible = False
        for p in papers:
            mine = {sec for (tt, pp, sec) in cg.taught if tt == tid and pp == p}
            if sections_writing.get(p, set()) - mine:
                possible = True
                break
        if not possible:
            exempt[tid] = "teaches every section of every paper they teach"
    return exempt


def presolve_check(ds: Dataset, pm: PaperMap, cg: ConflictGraph, layouts: list[RoomLayout]) -> FeasibilityReport:
    f: list[Finding] = []
    gap = ds.config.min_day_gap
    days = ds.config.exam_days()
    n_days = len(days)
    slots = n_days * len(ds.config.sessions)
    cap = slot_capacity(ds, layouts)
    per_room = int(ds.config["duties"]["invigilators_per_room"])

    f.append(Finding("info", "calendar",
                     f"{n_days} exam day(s) × {len(ds.config.sessions)} session(s) = {slots} slot(s); "
                     f"minimum gap between a student's exam days = {gap}"))
    f.append(Finding("info", "slot-capacity",
                     f"at most {cap.rooms_usable} of {len(layouts)} room(s) can open per slot "
                     f"(limited by {cap.limited_by}: {len(ds.teachers)} invigilator(s), {per_room} per room); "
                     f"they hold {cap.total} seats — {cap.cap_a} on side A, {cap.cap_b} on side B"))

    # 1. Temporal: per-student and clique lower bounds on exam days.
    per_student = Counter({s: len(p) for s, p in pm.student_papers.items()})
    worst = per_student.most_common(1)
    min_days = 0
    if worst:
        sid, k = worst[0]
        need = required_days(k, gap)
        min_days = need
        n_bad = sum(1 for v in per_student.values() if required_days(v, gap) > n_days)
        sev = "blocking" if need > n_days else "info"
        msg = (f"the busiest student ({sid}) writes {k} papers, needing ≥ {need} exam days at gap {gap}; "
               f"calendar has {n_days}")
        if sev == "blocking":
            msg += (f". {n_bad} student(s) cannot fit. Fix: extend the calendar by ≥ {need - n_days} exam day(s), "
                    f"or lower min_day_gap (with gap 1 they need {required_days(k, 1)} day(s))")
        f.append(Finding(sev, "student-day-bound", msg, [sid]))
    clique = cg.max_clique()
    if clique:
        need = required_days(len(clique), gap)
        min_days = max(min_days, need)
        if need > n_days:
            f.append(Finding("blocking", "conflict-clique",
                             f"{len(clique)} papers pairwise share students ({', '.join(clique)}); they need "
                             f"≥ {need} exam days but the calendar has {n_days}", clique))
        else:
            f.append(Finding("info", "conflict-clique",
                             f"largest group of mutually conflicting papers: {len(clique)} → ≥ {need} exam days"))

    # 2. Spatial: the largest paper must fit on one side of the usable rooms.
    over = [(p, pm.size(p)) for p in pm.paper_students if pm.size(p) > cap.cap_a]
    for p, n in sorted(over, key=lambda x: -x[1]):
        deficit = n - cap.cap_a
        avg_a = cap.cap_a / max(cap.rooms_usable, 1)
        more_rooms = math.ceil(deficit / max(avg_a, 1))
        what = (f"{more_rooms * per_room} more invigilator(s)" if cap.limited_by == "invigilators"
                else f"≈{more_rooms} more room(s)")
        f.append(Finding("blocking", "paper-too-large",
                         f"paper {p} has {n} students but one slot can seat at most {cap.cap_a} students of a single "
                         f"paper (no two neighbours may share a paper); short by {deficit} seat(s) — needs {what}",
                         [p]))

    # 3. Aggregate seats.
    demand = sum(pm.size(p) for p in pm.paper_students)
    supply = cap.total * slots
    if demand > supply:
        f.append(Finding("blocking", "total-seats",
                         f"{demand} paper-sittings but only {supply} seats across all slots; short by {demand - supply}"))
    else:
        f.append(Finding("info", "total-seats", f"{demand} paper-sittings vs {supply} seats across all slots "
                                                f"({100 * demand / max(supply, 1):.0f}% utilisation if fully spread)"))

    # 4. Duties: lower bound on room-slots vs the invigilator pool.
    if layouts:
        biggest = max(l.room.capacity for l in layouts)
        min_room_slots = math.ceil(demand / biggest)
        duty_demand = min_room_slots * per_room
        duty_supply = len(ds.teachers) * slots
        sev = "blocking" if duty_demand > duty_supply else "info"
        f.append(Finding(sev, "duty-pool", f"≥ {duty_demand} invigilation duties needed; pool supplies at most "
                                            f"{duty_supply} (1 per teacher per slot)"))
    if len(ds.teachers) < per_room:
        f.append(Finding("blocking", "duty-pool", f"only {len(ds.teachers)} teacher(s); each room needs {per_room}"))

    # 5. Coverage rule that cannot be met (reported, then exempted).
    if ds.config["duties"]["require_own_paper_duty"]:
        ex = coverage_exempt(ds, pm, cg)
        if ex:
            f.append(Finding("warning", "coverage-exempt",
                             f"{len(ex)} teacher(s) teach every section of their paper(s), so 'one duty on a paper "
                             f"you teach' is impossible for them; they are exempted: {', '.join(sorted(ex))}",
                             sorted(ex)))

    # 6. Pins that already break the gap rule against each other.
    pins = [p for p in ds.pins if p.kind == "paper_slot"]
    day_idx = {d.isoformat(): i for i, d in enumerate(days)}
    for i, a in enumerate(pins):
        for b in pins[i + 1:]:
            if a.paper_id != b.paper_id and cg.conflicts(a.paper_id, b.paper_id):
                if abs(day_idx[a.date] - day_idx[b.date]) < gap:
                    f.append(Finding("blocking", "pins-conflict",
                                     f"pins put conflicting papers {a.paper_id} and {b.paper_id} "
                                     f"{abs(day_idx[a.date] - day_idx[b.date])} day(s) apart (< {gap})",
                                     [a.paper_id, b.paper_id]))

    return FeasibilityReport(f, cap, min_days, n_days)

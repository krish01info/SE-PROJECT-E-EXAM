"""M4 — Scheduling Engine (C4, MoSCoW R4).

Stage 1 (papers → days) and stage 2 (days → sessions) are solved in one
CP-SAT model rather than one after the other. Solving them separately can
pick a day assignment that no session split can seat, which would need a
feedback loop; one model avoids that while keeping both stages' rules:

Hard
  * every paper sits in exactly one slot (all its course codes share it);
  * gap rule: if p and q share a student, |day(p) − day(q)| ≥ min_day_gap
    (Plan §4.2: the morning/evening rules collapse into this one day rule);
  * seating feasibility: each paper is put on side A or B; per slot, side-A
    students ≤ side-A seats of the usable rooms, same for B. This is the
    "no paper takes more than about half the seats" condition made exact;
  * pinned paper→slot overrides (C9).
Objective (lexicographic, two solves)
  1. minimise the span (last exam day used);
  2. with the span fixed, minimise the peak number of students in any one
     slot, which balances morning and evening seat demand.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .conflicts import ConflictGraph
from .feasibility import Diagnosis, Finding, SlotCapacity
from .mapping import PaperMap
from .model import Dataset, Slot


@dataclass
class ScheduleResult:
    ok: bool
    slot_of: dict[str, Slot] = field(default_factory=dict)
    side_of: dict[str, str] = field(default_factory=dict)  # paper -> "A" | "B"
    span_days: int = 0
    peak_load: int = 0
    status: str = ""
    seconds: float = 0.0
    diagnosis: Diagnosis | None = None


def _solver(ds: Dataset, limit: float) -> cp_model.CpSolver:
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(limit)
    s.parameters.num_workers = int(ds.config["solver"]["workers"])
    s.parameters.random_seed = int(ds.config["solver"]["seed"])
    return s


class _Model:
    def __init__(self, ds, pm, cg, cap, slots, papers, use_assumptions=False, hints=None):
        self.m = cp_model.CpModel()
        m = self.m
        self.papers, self.slots = papers, slots
        gap = ds.config.min_day_gap
        n_days = len(ds.config.exam_days())
        size = {p: pm.size(p) for p in papers}
        self.y = {(p, t): m.NewBoolVar(f"y_{p}_{t}") for p in papers for t in range(len(slots))}
        self.a = {p: m.NewBoolVar(f"sideA_{p}") for p in papers}
        self.groups: dict[str, tuple[str, list]] = {}  # literal name -> (kind, entities)
        self.lits: list = []

        def guard(name, kind, ents):
            if not use_assumptions:
                return None
            lit = m.NewBoolVar(name)
            self.groups[lit.Name()] = (kind, ents)
            self.lits.append(lit)
            return lit

        for p in papers:
            m.AddExactlyOne(self.y[p, t] for t in range(len(slots)))

        # day indicator
        self.dayb = {}
        for p in papers:
            for d in range(n_days):
                ts = [t for t, s in enumerate(slots) if s.day_index == d]
                self.dayb[p, d] = sum(self.y[p, t] for t in ts)

        # gap rule
        for (p, q) in cg.edges():
            if p not in self.a or q not in self.a:
                continue
            lit = guard(f"gap|{p}|{q}", "gap", [p, q])
            for d in range(n_days):
                window = [d2 for d2 in range(max(0, d - gap + 1), min(n_days, d + gap))]
                c = m.Add(self.dayb[p, d] + sum(self.dayb[q, d2] for d2 in window) <= 1)
                if lit is not None:
                    c.OnlyEnforceIf(lit)

        # seating capacity per slot and side
        self.load, self.side_a = [], []
        for t in range(len(slots)):
            za = []
            for p in papers:
                z = m.NewBoolVar(f"z_{p}_{t}")
                m.AddImplication(z, self.y[p, t])
                m.AddImplication(z, self.a[p])
                m.AddBoolOr([self.y[p, t].Not(), self.a[p].Not(), z])
                za.append((p, z))
            side_a = sum(size[p] * z for p, z in za)
            total = sum(size[p] * self.y[p, t] for p in papers)
            la = guard(f"capA|{t}", "capacity", [slots[t].key, "A"])
            lb = guard(f"capB|{t}", "capacity", [slots[t].key, "B"])
            c1 = m.Add(side_a <= cap.cap_a)
            c2 = m.Add(total - side_a <= cap.cap_b)
            if la is not None:
                c1.OnlyEnforceIf(la)
                c2.OnlyEnforceIf(lb)
            self.load.append(total)
            self.side_a.append(side_a)

        # pins
        idx = {(s.date.isoformat(), s.session): t for t, s in enumerate(slots)}
        for i, pin in enumerate(ds.pins):
            if pin.kind != "paper_slot" or pin.paper_id not in self.a:
                continue
            lit = guard(f"pin|{i}", "pin", [pin.describe()])
            c = m.Add(self.y[pin.paper_id, idx[(pin.date, pin.session)]] == 1)
            if lit is not None:
                c.OnlyEnforceIf(lit)

        # span
        self.last = m.NewIntVar(0, max(n_days - 1, 0), "last_day")
        for p in papers:
            for t, s in enumerate(slots):
                if s.day_index:
                    m.Add(self.last >= s.day_index).OnlyEnforceIf(self.y[p, t])
        self.peak = m.NewIntVar(0, sum(size.values()), "peak")
        for t in range(len(slots)):
            m.Add(self.peak >= self.load[t])
        # Rooms a slot needs ~ the fuller side divided by side-seats per room.
        per_room = max(1, cap.cap_a // max(cap.rooms_usable, 1))
        self.rooms = []
        for t in range(len(slots)):
            r = m.NewIntVar(0, cap.rooms_usable, f"rooms_{t}")
            m.Add(r * per_room >= self.side_a[t])
            m.Add(r * per_room >= self.load[t] - self.side_a[t])
            self.rooms.append(r)

        if hints:
            for p, t in hints.items():
                if p in self.a:
                    for tt in range(len(slots)):
                        m.AddHint(self.y[p, tt], int(tt == t))


def solve_schedule(ds: Dataset, pm: PaperMap, cg: ConflictGraph, cap: SlotCapacity,
                   hints: dict[str, str] | None = None) -> ScheduleResult:
    t0 = time.time()
    slots = ds.slots()
    papers = sorted(p for p in pm.paper_students if pm.size(p) > 0)
    limit = float(ds.config["scheduling"]["time_limit_s"])
    hint_idx = None
    if hints:
        key_to_t = {s.key: t for t, s in enumerate(slots)}
        hint_idx = {p: key_to_t[k] for p, k in hints.items() if k in key_to_t}

    mdl = _Model(ds, pm, cg, cap, slots, papers, hints=hint_idx)
    mdl.m.Minimize(mdl.last)
    s = _solver(ds, limit * 0.5)
    st = s.Solve(mdl.m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res = ScheduleResult(False, status=s.StatusName(st), seconds=time.time() - t0)
        if st == cp_model.INFEASIBLE:
            res.diagnosis = diagnose_schedule(ds, pm, cg, cap, slots, papers)
        else:
            res.diagnosis = Diagnosis("scheduling", f"solver stopped without a schedule ({s.StatusName(st)}); "
                                                    f"raise scheduling.time_limit_s")
        return res
    span = int(s.Value(mdl.last))
    first_status = s.StatusName(st)
    sol_slots = {p: next(t for t in range(len(slots)) if s.Value(mdl.y[p, t])) for p in papers}

    # Phase 2: fix span; open as few rooms as possible (every room costs two
    # invigilators), then balance the peak slot load.
    mdl2 = _Model(ds, pm, cg, cap, slots, papers, hints=sol_slots)
    mdl2.m.Add(mdl2.last <= span)
    mdl2.m.Minimize(10_000 * sum(mdl2.rooms) + mdl2.peak)
    s2 = _solver(ds, limit * 0.5)
    st2 = s2.Solve(mdl2.m)
    if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        s, mdl, status = s2, mdl2, f"span {first_status.lower()}, rooms/balance {s2.StatusName(st2).lower()}"
    else:
        status = first_status.lower()
    slot_of = {p: slots[next(t for t in range(len(slots)) if s.Value(mdl.y[p, t]))] for p in papers}
    side_of = {p: "A" if s.Value(mdl.a[p]) else "B" for p in papers}
    return ScheduleResult(True, slot_of, side_of, span + 1, int(s.Value(mdl.peak)), status, time.time() - t0)


def diagnose_schedule(ds, pm, cg, cap, slots, papers, budget_s: float = 60.0) -> Diagnosis:
    """C8: find a small set of rules that cannot all hold, and explain it."""
    t0 = time.time()
    mdl = _Model(ds, pm, cg, cap, slots, papers, use_assumptions=True)
    names = {lit.Name(): lit for lit in mdl.lits}
    s = _solver(ds, 20)
    mdl.m.AddAssumptions(mdl.lits)
    st = s.Solve(mdl.m)
    if st != cp_model.INFEASIBLE:
        return Diagnosis("scheduling", "no schedule found within the time limit, but no conflicting rule set "
                                       "was proven; try a longer time limit")
    core_idx = s.SufficientAssumptionsForInfeasibility()
    lit_by_index = {lit.Index(): lit for lit in mdl.lits}
    core = [lit_by_index[i].Name() for i in core_idx if i in lit_by_index]

    # Deletion filter to shrink the core while budget lasts.
    if len(core) <= 80:
        i = 0
        while i < len(core) and time.time() - t0 < budget_s:
            trial = core[:i] + core[i + 1:]
            m2 = _Model(ds, pm, cg, cap, slots, papers, use_assumptions=True)
            lits2 = {l.Name(): l for l in m2.lits}
            m2.m.AddAssumptions([lits2[n] for n in trial])
            s2 = _solver(ds, 5)
            if s2.Solve(m2.m) == cp_model.INFEASIBLE:
                core = trial
            else:
                i += 1

    findings = []
    gap_pairs = [mdl.groups[n][1] for n in core if mdl.groups[n][0] == "gap"]
    caps = [mdl.groups[n][1] for n in core if mdl.groups[n][0] == "capacity"]
    pins = [mdl.groups[n][1][0] for n in core if mdl.groups[n][0] == "pin"]
    g = ds.config.min_day_gap
    if gap_pairs:
        involved = sorted({p for pair in gap_pairs for p in pair})
        sample = []
        for p, q in gap_pairs[:6]:
            common = sorted(set(pm.paper_students[p]) & set(pm.paper_students[q]))
            sample.append(f"{p}–{q} ({len(common)} shared student(s), e.g. {common[0]})")
        findings.append(Finding("blocking", "gap-rule",
                                f"papers {', '.join(involved)} must be ≥ {g} exam day(s) apart pairwise "
                                f"for shared students; conflicting pairs: {'; '.join(sample)}", involved))
    if caps:
        findings.append(Finding("blocking", "slot-capacity",
                                f"{len(caps)} slot/side seat limit(s) involved (side A holds ≤ {cap.cap_a}, "
                                f"side B ≤ {cap.cap_b} per slot)", [f"{k}/{side}" for k, side in caps]))
    if pins:
        findings.append(Finding("blocking", "pinned-override", "pinned assignment(s) involved: " + "; ".join(pins),
                                pins))
    summary = ("No exam schedule satisfies all of the rules below at the same time. Relax one of them — "
               "remove or move a pin, extend the calendar, add rooms/invigilators, or lower min_day_gap.")
    return Diagnosis("scheduling", summary, findings)

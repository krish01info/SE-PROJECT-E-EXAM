"""M6 — Duty Engine (C6, MoSCoW R7 + R13).

Hard (SRS 2.4.1)
  * exactly ``invigilators_per_room`` (2) teachers per open room per slot;
  * at most one duty per teacher per slot;
  * own-class exclusion: no teacher in a room holding a student they taught
    *for the paper being written there* (taught-relation from M3);
  * coverage: every teaching staff member gets ≥ 1 duty in a room where a
    paper they teach is written (PhD scholars exempt; teachers for whom this
    is impossible are exempted and reported);
  * pinned teacher→room overrides (C9).
Soft (penalties)
  * ≤ ``max_duties_per_day_soft`` duty per teacher per day (weight 1000);
  * one in-domain + one out-of-domain invigilator per room (weight 100);
  * rank-weighted fairness: first minimise the highest weighted load
    (load ÷ rank weight), then narrow the gap to the lowest one.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .config import INVIGILATION_ONLY
from .conflicts import ConflictGraph
from .feasibility import Diagnosis, Finding, coverage_exempt
from .mapping import PaperMap
from .model import Dataset
from .seating import SeatingResult


@dataclass(frozen=True)
class Duty:
    slot_key: str
    room_id: str
    teacher_id: str
    in_domain: bool


@dataclass
class DutyResult:
    ok: bool
    duties: list[Duty] = field(default_factory=list)
    exempt: dict[str, str] = field(default_factory=dict)
    status: str = ""
    seconds: float = 0.0
    day_overloads: int = 0
    domain_mismatches: int = 0
    diagnosis: Diagnosis | None = None


def _solver(ds, limit):
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(limit)
    s.parameters.num_workers = int(ds.config["solver"]["workers"])
    s.parameters.random_seed = int(ds.config["solver"]["seed"])
    return s


class _DutyModel:
    def __init__(self, ds, pm, cg, seating, exempt, use_assumptions=False, hints=None):
        self.m = m = cp_model.CpModel()
        cfg = ds.config["duties"]
        per_room = int(cfg["invigilators_per_room"])
        weights = cfg["rank_weights"]
        by_room = seating.by_room()
        self.rs = sorted(by_room, key=lambda k: (seating.slots[k[0]], k[1]))
        self.content = {rs: {(a.paper_id, a.section_id) for a in by_room[rs]} for rs in self.rs}
        self.room_papers = {rs: {p for p, _ in self.content[rs]} for rs in self.rs}
        room_domains = {rs: {ds.papers[p].department for p in self.room_papers[rs]} for rs in self.rs}
        taught_by = defaultdict(set)
        for t, p, sec in cg.taught:
            taught_by[t].add((p, sec))
        self.teachers = sorted(ds.teachers)
        self.groups: dict[str, tuple[str, list]] = {}
        self.lits = []

        def guard(name, kind, ents):
            if not use_assumptions:
                return None
            lit = m.NewBoolVar(name)
            self.groups[name] = (kind, ents)
            self.lits.append(lit)
            return lit

        self.x = {}
        self.excluded_count = defaultdict(int)
        for rs in self.rs:
            for t in self.teachers:
                if taught_by[t] & self.content[rs]:
                    self.excluded_count[rs] += 1
                    continue
                self.x[t, rs] = m.NewBoolVar(f"x_{t}_{rs[0]}_{rs[1]}")
        self.in_domain = {(t, rs): ds.teachers[t].department in room_domains[rs] for (t, rs) in self.x}

        # staffing
        self.understaffed = []
        for rs in self.rs:
            vs = [self.x[t, rs] for t in self.teachers if (t, rs) in self.x]
            if len(vs) < per_room:
                self.understaffed.append(rs)
            lit = guard(f"staff|{rs[0]}|{rs[1]}", "staffing", [f"{rs[1]} @ {rs[0]}"])
            c = m.Add(sum(vs) == per_room)
            if lit is not None:
                c.OnlyEnforceIf(lit)
        # one duty per teacher per slot
        slots = sorted({rs[0] for rs in self.rs})
        for t in self.teachers:
            for sk in slots:
                vs = [self.x[t, rs] for rs in self.rs if rs[0] == sk and (t, rs) in self.x]
                if len(vs) > 1:
                    m.AddAtMostOne(vs)
        # coverage
        self.runtime_exempt = {}
        if cfg["require_own_paper_duty"]:
            for t in self.teachers:
                if ds.teachers[t].rank in INVIGILATION_ONLY or t in exempt or t not in cg.teacher_papers:
                    continue
                vs = [self.x[t, rs] for rs in self.rs
                      if (t, rs) in self.x and self.room_papers[rs] & cg.teacher_papers[t]]
                if not vs:
                    self.runtime_exempt[t] = "every room writing their paper(s) holds a section they taught"
                    continue
                lit = guard(f"cover|{t}", "coverage", [t])
                c = m.Add(sum(vs) >= 1)
                if lit is not None:
                    c.OnlyEnforceIf(lit)
        # pins
        self.pin_problems = []
        for i, pin in enumerate(ds.pins):
            if pin.kind != "teacher_room":
                continue
            rs = (f"{pin.date}_{pin.session}", pin.room_id)
            if rs not in self.content:
                self.pin_problems.append(f"{pin.describe()}: that room is not open in that slot")
                continue
            if (pin.teacher_id, rs) not in self.x:
                self.pin_problems.append(f"{pin.describe()}: the room holds a section they taught for that paper")
                continue
            lit = guard(f"pin|{i}", "pin", [pin.describe()])
            c = m.Add(self.x[pin.teacher_id, rs] == 1)
            if lit is not None:
                c.OnlyEnforceIf(lit)

        # loads and soft terms
        by_t, by_rs = defaultdict(list), defaultdict(list)
        for (t, rs), v in self.x.items():
            by_t[t].append((rs, v))
            by_rs[rs].append((t, v))
        self.load = {t: sum(v for _, v in by_t[t]) for t in self.teachers}
        max_load = len(slots)
        self.scale = {t: int(round(100 / float(weights[ds.teachers[t].rank]))) for t in self.teachers}
        self.zmax = m.NewIntVar(0, max_load * max(self.scale.values()), "zmax")
        self.zmin = m.NewIntVar(0, max_load * max(self.scale.values()), "zmin")
        for t in self.teachers:
            m.Add(self.load[t] * self.scale[t] <= self.zmax)
            m.Add(self.load[t] * self.scale[t] >= self.zmin)

        cap_day = int(cfg["max_duties_per_day_soft"])
        day_of = {rs: rs[0].split("_")[0] for rs in self.rs}
        self.overs = []
        for t in self.teachers:
            per_day = defaultdict(list)
            for rs, v in by_t[t]:
                per_day[day_of[rs]].append(v)
            for d, vs in sorted(per_day.items()):
                if len(vs) > cap_day:
                    o = m.NewIntVar(0, len(vs), f"over_{t}_{d}")
                    m.Add(o >= sum(vs) - cap_day)
                    self.overs.append(o)
        self.devs = []
        if per_room == 2:
            for rs in self.rs:
                inc = sum(v for t, v in by_rs[rs] if self.in_domain[t, rs])
                dev = m.NewIntVar(0, 2, f"dom_{rs[0]}_{rs[1]}")
                m.Add(dev >= inc - 1)
                m.Add(dev >= 1 - inc)
                self.devs.append(dev)
        if hints:
            for key, v in self.x.items():
                m.AddHint(v, int(key in hints))


def assign_duties(ds: Dataset, pm: PaperMap, cg: ConflictGraph, seating: SeatingResult,
                  hints: set | None = None) -> DutyResult:
    t0 = time.time()
    limit = float(ds.config["duties"]["time_limit_s"])
    exempt = coverage_exempt(ds, pm, cg) if ds.config["duties"]["require_own_paper_duty"] else {}
    mdl = _DutyModel(ds, pm, cg, seating, exempt, hints=hints)
    exempt = {**exempt, **mdl.runtime_exempt}

    quick = []
    for rs in mdl.understaffed:
        quick.append(Finding("blocking", "understaffed-room",
                             f"room {rs[1]} at {rs[0]}: {mdl.excluded_count[rs]} teacher(s) are excluded (they taught "
                             f"a section seated there) leaving fewer than "
                             f"{ds.config['duties']['invigilators_per_room']} eligible", [rs[1], rs[0]]))
    for msg in mdl.pin_problems:
        quick.append(Finding("blocking", "pinned-override", msg))
    if quick:
        return DutyResult(False, exempt=exempt, status="INFEASIBLE", seconds=time.time() - t0,
                          diagnosis=Diagnosis("duties", "Invigilation rules cannot all be met.", quick))

    # Phase 1: minimise the highest weighted load.
    mdl.m.Minimize(mdl.zmax)
    s = _solver(ds, limit * 0.4)
    st = s.Solve(mdl.m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        diag = diagnose_duties(ds, pm, cg, seating, exempt) if st == cp_model.INFEASIBLE else \
            Diagnosis("duties", f"solver stopped without a roster ({s.StatusName(st)}); raise duties.time_limit_s")
        return DutyResult(False, exempt=exempt, status=s.StatusName(st), seconds=time.time() - t0, diagnosis=diag)
    zstar = int(s.Value(mdl.zmax))
    first = {k for k, v in mdl.x.items() if s.Value(v)}

    # Phase 2: keep that ceiling, minimise soft penalties and the fairness gap.
    mdl2 = _DutyModel(ds, pm, cg, seating, exempt, hints=first)
    mdl2.m.Add(mdl2.zmax <= zstar)
    mdl2.m.Minimize(1000 * sum(mdl2.overs) + 100 * sum(mdl2.devs) + (mdl2.zmax - mdl2.zmin))
    s2 = _solver(ds, limit * 0.6)
    st2 = s2.Solve(mdl2.m)
    if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        s, mdl, status = s2, mdl2, f"fairness {s.StatusName(st).lower()}, soft rules {s2.StatusName(st2).lower()}"
    else:
        status = s.StatusName(st).lower()
    duties = [Duty(rs[0], rs[1], t, mdl.in_domain[t, rs]) for (t, rs), v in mdl.x.items() if s.Value(v)]
    duties.sort(key=lambda d: (d.slot_key, d.room_id, d.teacher_id))
    return DutyResult(True, duties, exempt, status, time.time() - t0,
                      day_overloads=int(sum(s.Value(o) for o in mdl.overs)),
                      domain_mismatches=int(sum(s.Value(d) for d in mdl.devs)))


def diagnose_duties(ds, pm, cg, seating, exempt) -> Diagnosis:
    mdl = _DutyModel(ds, pm, cg, seating, exempt, use_assumptions=True)
    mdl.m.AddAssumptions(mdl.lits)
    s = _solver(ds, 30)
    if s.Solve(mdl.m) != cp_model.INFEASIBLE:
        return Diagnosis("duties", "no roster found in time, but no conflicting rule set was proven")
    idx = {l.Index(): l.Name() for l in mdl.lits}
    core = [idx[i] for i in s.SufficientAssumptionsForInfeasibility() if i in idx]
    kinds = defaultdict(list)
    for n in core:
        kind, ents = mdl.groups[n]
        kinds[kind] += ents
    findings = []
    if kinds["staffing"]:
        slots = sorted({e.split(" @ ")[1] for e in kinds["staffing"]})
        findings.append(Finding("blocking", "staffing",
                                f"{len(kinds['staffing'])} room(s) in slot(s) {', '.join(slots[:6])} cannot all get "
                                f"two eligible invigilators at once", kinds["staffing"][:20]))
    if kinds["coverage"]:
        findings.append(Finding("blocking", "coverage",
                                f"teacher(s) {', '.join(kinds['coverage'][:15])} cannot all get a duty on a paper "
                                f"they teach alongside the other rules", kinds["coverage"]))
    if kinds["pin"]:
        findings.append(Finding("blocking", "pinned-override", "; ".join(kinds["pin"]), kinds["pin"]))
    return Diagnosis("duties", "No invigilation roster satisfies these rules together. Add invigilators, "
                               "move a paper to a quieter slot, or remove a pin.", findings)

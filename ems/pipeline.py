"""EMS Controller — runs M1→M9 and drives the Exam Plan state machine.

Follows the Design Lab sequence diagram for *Generate Exam Schedule*: get the
conflict graph, run the included pre-solve feasibility check (break on a
shortfall), fetch pins, solve, and on failure hand over to diagnostics.
"""
from __future__ import annotations

import csv
import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import plan as P
from .config import Config
from .conflicts import build_conflicts
from .duties import assign_duties
from .feasibility import presolve_check
from .geometry import layouts_for
from .ingest import ValidationError, format_issues, load_dataset
from .mapping import build_paper_map
from .reports import write_csvs, write_html
from .scheduling import solve_schedule
from .seating import allocate_seating
from .verify import format_verification, verify_plan


OUTPUT_FILES = ("schedule.csv", "seating.csv", "duties.csv", "student_timetables.csv", "teacher_rosters.csv",
                "slot_summary.csv", "fairness.csv", "run.json", "verification.json", "verification.txt",
                "diagnosis.txt", "feasibility_report.txt", "validation_report.txt")


@dataclass
class RunResult:
    ok: bool
    state: str
    out_dir: Path
    messages: list[str] = field(default_factory=list)
    verification: dict | None = None


def _read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def run_pipeline(dataset_dir, out_dir, pins_file=None, overrides: dict | None = None, fresh=False,
                 force=False, log=print) -> RunResult:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prev = P.ExamPlan.load(out)
    if prev and prev.locked and not force:
        msg = (f"The plan in {out} is '{prev.state}' and may not change. Use a new output directory, "
               f"or --force to overwrite an approved plan.")
        return RunResult(False, prev.state, out, [msg])
    plan = P.ExamPlan()
    t0 = time.time()
    msgs: list[str] = []

    def say(m):
        msgs.append(m)
        log(m)

    def finish(ok):
        plan.save(out)
        return RunResult(ok, plan.state, out, msgs)

    # Previous plan -> solver hints (stability across re-solves), then clear old outputs so a failed
    # run never leaves an earlier plan looking current.
    hints_s, hints_d = None, None
    if not fresh:
        hints_s = {r["paper_id"]: f"{r['date']}_{r['session']}" for r in _read_csv(out / "schedule.csv")} or None
        hints_d = {(r["teacher_id"], (f"{r['date']}_{r['session']}", r["room_id"]))
                   for r in _read_csv(out / "duties.csv")} or None
    for stale in OUTPUT_FILES:
        (out / stale).unlink(missing_ok=True)
    shutil.rmtree(out / "reports", ignore_errors=True)

    # M1 / M2 ----------------------------------------------------------------
    try:
        ds = load_dataset(dataset_dir, pins_file=pins_file)
    except ValidationError as e:
        (out / "validation_report.txt").write_text(e.report() + "\n")
        say(e.report())
        say("Dataset rejected; nothing was solved.")
        return finish(False)
    if overrides:
        ds.config = ds.config.with_overrides(**overrides)
    (out / "validation_report.txt").write_text(format_issues(ds.issues) + "\n")
    pm = build_paper_map(ds)
    plan.fire("dataset validated and mapped",
              f"{len(ds.students)} students, {len(pm.paper_students)} papers, {len(ds.course_codes)} codes")
    say(f"[1/6] Validated {ds.config.name}: {len(ds.students)} students, {len(pm.paper_students)} papers "
        f"({len(ds.course_codes)} course codes, {len(pm.shared_papers)} shared), {len(ds.teachers)} teachers, "
        f"{len(ds.rooms)} rooms, {len(ds.pins)} pin(s); {len(ds.issues)} warning(s)")

    # M3 / M7 pre-solve ----------------------------------------------------------
    cg = build_conflicts(ds, pm)
    layouts = layouts_for(ds.rooms, ds.config["seating"])
    rep = presolve_check(ds, pm, cg, layouts)
    (out / "feasibility_report.txt").write_text(rep.text() + "\n")
    if not rep.ok:
        plan.fire("feasibility check [shortfall] / report deficit")
        say(rep.text())
        return finish(False)
    plan.fire("feasibility check [capacity sufficient]")
    say(f"[2/6] Feasibility check passed: ≥ {rep.min_days_needed} of {rep.days_available} exam days needed; "
        f"{rep.capacity.rooms_usable} rooms usable per slot ({rep.capacity.total} seats)")

    # M4 --------------------------------------------------------------------------
    sched = solve_schedule(ds, pm, cg, rep.capacity, hints=hints_s)
    if not sched.ok:
        plan.fire("generate schedule [no valid days] / diagnose")
        (out / "diagnosis.txt").write_text(sched.diagnosis.text() + "\n")
        say(sched.diagnosis.text())
        return finish(False)
    plan.fire("generate schedule [2-day gap met]")
    say(f"[3/6] Schedule: {len(sched.slot_of)} papers in {len({s.key for s in sched.slot_of.values()})} slots "
        f"over {sched.span_days} exam days ({sched.status}, {sched.seconds:.0f}s)")

    # M5 --------------------------------------------------------------------------
    seating = allocate_seating(ds, pm, sched, rep.capacity)
    if not seating.ok:
        plan.fire("allocate seats [not enough seats] / diagnose")
        (out / "diagnosis.txt").write_text(seating.diagnosis.text() + "\n")
        say(seating.diagnosis.text())
        return finish(False)
    plan.fire("allocate seats [no adjacent same paper]")
    say(f"[4/6] Seating: {len(seating.seats)} sittings in "
        f"{sum(len(v) for v in seating.rooms_open.values())} room-slots")

    # M6 --------------------------------------------------------------------------
    duties = assign_duties(ds, pm, cg, seating, hints=hints_d)
    if not duties.ok:
        plan.fire("assign duties [rules unsatisfiable] / diagnose")
        write_csvs(out, ds, pm, cg, sched, seating, None, rep.capacity)
        (out / "diagnosis.txt").write_text(duties.diagnosis.text() + "\n")
        say(duties.diagnosis.text())
        return finish(False)
    plan.fire("assign duties [exclusion & coverage met]")
    say(f"[5/6] Duties: {len(duties.duties)} invigilation duties ({duties.status}, {duties.seconds:.0f}s); "
        f"{duties.day_overloads} teacher-day overload(s), {duties.domain_mismatches} domain-pairing miss(es)")

    # M9 --------------------------------------------------------------------------
    tables = write_csvs(out, ds, pm, cg, sched, seating, duties, rep.capacity)
    stats = {
        "papers": len(sched.slot_of), "students": len(ds.students), "sittings": len(seating.seats),
        "span_days": sched.span_days, "slots_used": len(seating.rooms_open), "duties": len(duties.duties),
        "room_slots": sum(len(v) for v in seating.rooms_open.values()),
    }
    run = {
        "dataset": _portable(dataset_dir),
        "pins_file": _portable(pins_file) if pins_file else None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": ds.config.raw,
        "stats": stats,
        "coverage_exempt": duties.exempt,
        "solver": {"schedule": sched.status, "duties": duties.status,
                   "seconds": round(time.time() - t0, 1)},
    }
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    ver = verify_plan(out)
    (out / "verification.txt").write_text(format_verification(ver) + "\n")
    plan.fire("generate reports")
    write_html(out, ds, pm, cg, sched, seating, duties, rep.capacity,
               {"tables": tables, "verification": ver, "state": plan.state, "stats": stats})
    say(f"[6/6] Reports written to {out}/reports/index.html — verification: "
        f"{'all hard rules pass' if ver['all_passed'] else 'FAILURES (see verification.txt)'}")
    res = finish(ver["all_passed"])
    res.verification = ver
    return res


def _portable(path) -> str:
    """Relative to the working directory when possible, so committed plans verify on any machine."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(p)


def transition(out_dir, event: str, note: str = "") -> str:
    """Apply a manual state transition (HoD approval / change request)."""
    plan = P.ExamPlan.load(Path(out_dir))
    if plan is None:
        raise P.TransitionError(f"no plan found in {out_dir}; run `solve` first")
    new = plan.fire(event, note)
    plan.save(Path(out_dir))
    _restamp_index(Path(out_dir), new)
    return new


def _restamp_index(out: Path, state: str):
    idx = out / "reports" / "index.html"
    if idx.exists():
        import re
        s = idx.read_text()
        s = re.sub(r"Plan state: <b>[^<]*</b>", f"Plan state: <b>{state}</b>", s, count=1)
        idx.write_text(s)


def effective_config(out_dir) -> Config | None:
    p = Path(out_dir) / "run.json"
    return Config(json.loads(p.read_text())["config"]) if p.exists() else None

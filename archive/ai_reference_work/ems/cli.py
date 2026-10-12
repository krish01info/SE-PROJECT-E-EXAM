"""Command-line interface (MoSCoW R17: terminal based, fixed input/output).

    python -m ems validate data/dummy
    python -m ems check    data/dummy
    python -m ems solve    data/dummy -o out/dummy
    python -m ems verify   out/dummy
    python -m ems pin      data/dummy paper DSA --date 2026-03-09 --session Morning
    python -m ems pin      data/dummy teacher T007 --room M03 --date 2026-03-09 --session Morning
    python -m ems pins     data/dummy            # list pins
    python -m ems unpin    data/dummy 1          # remove pin #1
    python -m ems approve  out/dummy             # HoD approves -> Approved (Locked)
    python -m ems request-changes out/dummy      # HoD sends the plan back
    python -m ems status   out/dummy
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import plan as P
from .conflicts import build_conflicts
from .feasibility import presolve_check
from .geometry import layouts_for
from .ingest import PIN_SCHEMA, ValidationError, format_issues, load_dataset
from .mapping import build_paper_map
from .pipeline import run_pipeline, transition
from .verify import format_verification, verify_plan


def _parse_set(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--set expects key=value, got {it!r}")
        k, v = it.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def _pins_path(args) -> Path:
    return Path(args.pins) if getattr(args, "pins", None) else Path(args.dataset) / "pins.csv"


def cmd_validate(a):
    try:
        ds = load_dataset(a.dataset, pins_file=a.pins)
    except ValidationError as e:
        print(e.report())
        return 1
    print(format_issues(ds.issues))
    pm = build_paper_map(ds)
    print(f"OK — {len(ds.students)} students, {len(ds.sections)} sections, {len(ds.teachers)} teachers, "
          f"{len(pm.paper_students)} papers from {len(ds.course_codes)} course codes, {len(ds.rooms)} rooms, "
          f"{len(ds.registrations)} registrations")
    for p, codes in sorted(pm.shared_papers.items()):
        print(f"  paper {p} is offered under {len(codes)} codes: {', '.join(codes)} → treated as one paper")
    return 0


def cmd_check(a):
    try:
        ds = load_dataset(a.dataset, pins_file=a.pins)
    except ValidationError as e:
        print(e.report())
        return 1
    if a.set:
        ds.config = ds.config.with_overrides(**_parse_set(a.set))
    pm = build_paper_map(ds)
    cg = build_conflicts(ds, pm)
    rep = presolve_check(ds, pm, cg, layouts_for(ds.rooms, ds.config["seating"]))
    print(rep.text())
    return 0 if rep.ok else 2


def cmd_solve(a):
    out = Path(a.out) if a.out else Path("out") / Path(a.dataset).name
    res = run_pipeline(a.dataset, out, pins_file=a.pins, overrides=_parse_set(a.set), fresh=a.fresh,
                       force=a.force, log=print)
    print(f"Plan state: {res.state}")
    if res.ok:
        print(f"Open {out / 'reports' / 'index.html'} in a browser to view or print the plan.")
    return 0 if res.ok else 2


def cmd_verify(a):
    v = verify_plan(a.out_dir, a.data)
    print(format_verification(v))
    return 0 if v["all_passed"] else 2


def cmd_pin(a):
    path = _pins_path(a)
    rows = []
    if path.exists():
        with path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
    row = {k: "" for k in PIN_SCHEMA}
    row.update(date=a.date, session=a.session)
    if a.what == "paper":
        row.update(kind="paper_slot", paper_id=a.id)
    else:
        if not a.room:
            raise SystemExit("teacher pins need --room")
        row.update(kind="teacher_room", teacher_id=a.id, room_id=a.room)
    rows.append(row)
    _write_pins(path, rows)
    try:  # validate immediately so a bad pin is caught now, not at solve time
        load_dataset(a.dataset, pins_file=path)
    except ValidationError as e:
        rows.pop()
        _write_pins(path, rows)
        print(e.report())
        print("Pin rejected and not saved.")
        return 1
    print(f"Saved pin #{len(rows)} to {path}. Re-run `solve` to re-plan around it.")
    return 0


def _write_pins(path: Path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PIN_SCHEMA)
        w.writeheader()
        w.writerows(rows)


def cmd_pins(a):
    path = _pins_path(a)
    if not path.exists():
        print("No pins.")
        return 0
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    for i, r in enumerate(rows, 1):
        what = (f"paper {r['paper_id']}" if r["kind"] == "paper_slot"
                else f"teacher {r['teacher_id']} → room {r['room_id']}")
        print(f"#{i}: {what} @ {r['date']} {r['session']}")
    return 0


def cmd_unpin(a):
    path = _pins_path(a)
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not 1 <= a.index <= len(rows):
        raise SystemExit(f"no pin #{a.index}")
    rows.pop(a.index - 1)
    _write_pins(path, rows)
    print(f"Removed pin #{a.index}.")
    return 0


def cmd_state(event):
    def run(a):
        try:
            print(f"Plan state: {transition(a.out_dir, event, a.note or '')}")
            return 0
        except P.TransitionError as e:
            print(e)
            return 1
    return run


def cmd_status(a):
    plan = P.ExamPlan.load(Path(a.out_dir))
    if not plan:
        print("No plan here yet.")
        return 1
    print(f"Plan state: {plan.state}")
    for h in plan.history:
        print(f"  {h['at']}  {h['from']} --[{h['event']}]--> {h['to']}" + (f"  ({h['note']})" if h["note"] else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ems", description="Exam Management System — scheduling, seating "
                                 "and invigilation duties from CSV inputs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def data_cmd(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("dataset", help="dataset directory")
        p.add_argument("--pins", help="pins CSV (default: <dataset>/pins.csv)")
        p.set_defaults(fn=fn)
        return p

    data_cmd("validate", cmd_validate, "C1/C2: validate inputs and show the course-code → paper mapping")
    p = data_cmd("check", cmd_check, "C7: pre-solve feasibility check")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="override config, e.g. scheduling.min_day_gap=1")
    p = data_cmd("solve", cmd_solve, "run the full pipeline and write outputs + reports")
    p.add_argument("-o", "--out", help="output directory (default out/<dataset name>)")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="override config, e.g. scheduling.min_day_gap=1")
    p.add_argument("--fresh", action="store_true", help="ignore the previous plan in OUT (no solver hints)")
    p.add_argument("--force", action="store_true", help="allow overwriting an approved (locked) plan")

    p = sub.add_parser("verify", help="independently re-check every hard rule on a finished plan")
    p.add_argument("out_dir")
    p.add_argument("--data", help="dataset directory (default: the one recorded in run.json)")
    p.set_defaults(fn=cmd_verify)

    p = data_cmd("pin", cmd_pin, "C9: pin a paper to a slot or a teacher to a room")
    p.add_argument("what", choices=["paper", "teacher"])
    p.add_argument("id", help="paper_id or teacher_id")
    p.add_argument("--date", required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--room")
    data_cmd("pins", cmd_pins, "list pins")
    p = data_cmd("unpin", cmd_unpin, "remove a pin by its number")
    p.add_argument("index", type=int)

    for name, event, h in [("approve", "HoD approves / publish plan", "HoD approves and locks the plan"),
                           ("request-changes", "HoD requests changes", "HoD sends the reported plan back"),
                           ("close", "exam period ends", "mark an approved plan's exam period as ended")]:
        p = sub.add_parser(name, help=h)
        p.add_argument("out_dir")
        p.add_argument("--note")
        p.set_defaults(fn=cmd_state(event))
    p = sub.add_parser("status", help="show plan state and its transition history")
    p.add_argument("out_dir")
    p.set_defaults(fn=cmd_status)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

"""The Exam Plan object and its state machine (Design Lab §4).

Transitions are written ``event [condition] / action`` exactly as in the
state transition table; any transition not in that table raises, so the code
cannot (say) seat an unscheduled plan or approve an unreported one.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

NOT_GENERATED = "Not Generated"
FEASIBILITY_CHECKED = "Feasibility Checked"
SCHEDULED = "Scheduled"
SEATED = "Seated"
DUTIES_ASSIGNED = "Duties Assigned"
REPORTED = "Reported"
APPROVED = "Approved (Locked)"
INF_CAPACITY = "Infeasible: Capacity"
INF_SCHEDULE = "Infeasible: Schedule"
INF_SEATING = "Infeasible: Seating"
INF_DUTIES = "Infeasible: Duties"
END = "End"

# (from, event) -> to
TRANSITIONS: dict[tuple[str, str], str] = {
    ("Start", "dataset validated and mapped"): NOT_GENERATED,
    (NOT_GENERATED, "feasibility check [capacity sufficient]"): FEASIBILITY_CHECKED,
    (NOT_GENERATED, "feasibility check [shortfall] / report deficit"): INF_CAPACITY,
    (INF_CAPACITY, "rooms or teachers added"): NOT_GENERATED,
    (FEASIBILITY_CHECKED, "generate schedule [2-day gap met]"): SCHEDULED,
    (FEASIBILITY_CHECKED, "generate schedule [no valid days] / diagnose"): INF_SCHEDULE,
    (INF_SCHEDULE, "pin paper to slot / re-solve"): FEASIBILITY_CHECKED,
    (SCHEDULED, "allocate seats [no adjacent same paper]"): SEATED,
    (SCHEDULED, "allocate seats [not enough seats] / diagnose"): INF_SEATING,
    (INF_SEATING, "pin paper to another slot / re-solve"): FEASIBILITY_CHECKED,
    (SEATED, "assign duties [exclusion & coverage met]"): DUTIES_ASSIGNED,
    (SEATED, "assign duties [rules unsatisfiable] / diagnose"): INF_DUTIES,
    (INF_DUTIES, "pin teacher to room / re-solve"): SEATED,
    (DUTIES_ASSIGNED, "staff pins teacher to room / re-solve"): SEATED,
    (DUTIES_ASSIGNED, "staff pins paper to slot / re-solve"): FEASIBILITY_CHECKED,
    (DUTIES_ASSIGNED, "generate reports"): REPORTED,
    (REPORTED, "HoD requests changes"): DUTIES_ASSIGNED,
    (REPORTED, "HoD approves / publish plan"): APPROVED,
    (APPROVED, "exam period ends"): END,
}


class TransitionError(RuntimeError):
    pass


class ExamPlan:
    def __init__(self, state: str = "Start", history: list | None = None):
        self.state = state
        self.history: list[dict] = history or []

    def fire(self, event: str, note: str = "") -> str:
        key = (self.state, event)
        if key not in TRANSITIONS:
            allowed = [e for (s, e) in TRANSITIONS if s == self.state]
            raise TransitionError(f"'{event}' is not allowed in state '{self.state}'. Allowed: {allowed}")
        new = TRANSITIONS[key]
        self.history.append({"at": datetime.now().isoformat(timespec="seconds"), "from": self.state,
                             "event": event, "to": new, "note": note})
        self.state = new
        return new

    @property
    def locked(self) -> bool:
        return self.state in (APPROVED, END)

    def save(self, out_dir: Path):
        (Path(out_dir) / "plan_state.json").write_text(
            json.dumps({"state": self.state, "history": self.history}, indent=2) + "\n")

    @classmethod
    def load(cls, out_dir: Path) -> "ExamPlan | None":
        p = Path(out_dir) / "plan_state.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return cls(d["state"], d["history"])

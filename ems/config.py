"""Run configuration (one ``config.json`` per dataset directory).

Every policy decision that the Phase 0 plan lists as an *open question* is a
configuration value here rather than a hard-coded rule, so the examination
cell can change policy without changing code.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

DEFAULTS: dict = {
    "name": "Unnamed dataset",
    "calendar": {
        "start": "2026-03-02",
        "end": "2026-03-27",
        # 0 = Monday ... 6 = Sunday
        "weekdays": [0, 1, 2, 3, 4],
        "holidays": [],
        "sessions": ["Morning", "Evening"],
    },
    "scheduling": {
        # Hard rule (SRS 2.4.1): no student writes two papers on exam days
        # less than ``min_day_gap`` apart. 2 = "one clear day in between".
        "min_day_gap": 2,
        # Day distance is measured in exam days (weekends/holidays skipped).
        "time_limit_s": 60,
    },
    "seating": {
        # Open question 1 -> resolved by MoSCoW R5 ("same row or column").
        "front_back_adjacent": True,
        # Students on neighbouring benches across an aisle count as adjacent.
        "across_aisle_adjacent": True,
        # Soft cap (open question 4): only reported, never enforced.
        "max_papers_per_room_soft": 4,
    },
    "duties": {
        "invigilators_per_room": 2,
        # Open question 3: rank-weighted fairness. Weight = relative share of
        # duties; PhD scholars weighted lower as the plan specifies.
        "rank_weights": {
            "professor": 0.7,
            "associate": 0.85,
            "assistant": 1.0,
            "phd": 0.5,
            "staff": 0.5,  # invigilation-only non-teaching staff
        },
        # Hard rule: each teaching staff member gets >= 1 duty on a paper they
        # teach (PhD scholars exempt). Teachers for whom this is impossible
        # (they teach every section of every paper they teach) are reported
        # and exempted rather than making the whole plan infeasible.
        "require_own_paper_duty": True,
        "max_duties_per_day_soft": 1,
        "time_limit_s": 90,
    },
    "validation": {
        "student_id_pattern": r"^[A-Z0-9][A-Z0-9_-]*$",
        "teacher_id_pattern": r"^[A-Z0-9][A-Z0-9_-]*$",
    },
    "solver": {"workers": 8, "seed": 7},
}

RANKS = ("professor", "associate", "assistant", "phd", "staff")
# Ranks exempt from the "one duty on a paper you teach" rule.
INVIGILATION_ONLY = ("phd", "staff")


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    raw: dict = field(default_factory=lambda: copy.deepcopy(DEFAULTS))

    @classmethod
    def load(cls, dataset_dir: Path) -> "Config":
        path = Path(dataset_dir) / "config.json"
        user = json.loads(path.read_text()) if path.exists() else {}
        return cls(_merge(DEFAULTS, user))

    def __getitem__(self, key):
        return self.raw[key]

    @property
    def name(self) -> str:
        return self.raw["name"]

    def exam_days(self) -> list[date]:
        cal = self.raw["calendar"]
        start = date.fromisoformat(cal["start"])
        end = date.fromisoformat(cal["end"])
        holidays = {date.fromisoformat(h) for h in cal.get("holidays", [])}
        days, d = [], start
        while d <= end:
            if d.weekday() in cal["weekdays"] and d not in holidays:
                days.append(d)
            d += timedelta(days=1)
        return days

    @property
    def sessions(self) -> list[str]:
        return list(self.raw["calendar"]["sessions"])

    @property
    def min_day_gap(self) -> int:
        return int(self.raw["scheduling"]["min_day_gap"])

    def with_overrides(self, **dotted) -> "Config":
        """Return a copy with ``section.key=value`` overrides applied."""
        raw = copy.deepcopy(self.raw)
        for dotted_key, value in dotted.items():
            parts = dotted_key.split(".")
            node = raw
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = value
        return Config(raw)

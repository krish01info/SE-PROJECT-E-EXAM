"""M2 — Canonical Paper Mapping (C2, MoSCoW R3).

Registrations and teaching assignments arrive keyed by *course code*. Every
downstream module reasons about *papers*. This module resolves the
many-to-one mapping once, so two offerings of the same paper under different
codes (e.g. Discrete Mathematics for 2nd and 3rd year) are always scheduled
in one slot and never seated next to each other.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .model import Dataset


@dataclass
class PaperMap:
    code_to_paper: dict[str, str]
    paper_codes: dict[str, list[str]]  # paper -> its course codes
    paper_students: dict[str, list[str]]  # paper -> students, roll order
    student_papers: dict[str, set[str]]  # student -> papers
    shared_papers: dict[str, list[str]] = field(default_factory=dict)  # papers with >1 code

    def size(self, paper_id: str) -> int:
        return len(self.paper_students.get(paper_id, []))


def build_paper_map(ds: Dataset) -> PaperMap:
    code_to_paper = {c: cc.paper_id for c, cc in ds.course_codes.items()}
    paper_codes: dict[str, list[str]] = defaultdict(list)
    for code, pid in sorted(code_to_paper.items()):
        paper_codes[pid].append(code)

    paper_students: dict[str, set[str]] = defaultdict(set)
    student_papers: dict[str, set[str]] = defaultdict(set)
    for sid, code in ds.registrations:
        pid = code_to_paper[code]
        paper_students[pid].add(sid)
        student_papers[sid].add(pid)

    shared = {p: codes for p, codes in paper_codes.items() if len(codes) > 1}
    return PaperMap(
        code_to_paper=code_to_paper,
        paper_codes=dict(paper_codes),
        # Roll order = lexical order of the roll number.
        paper_students={p: sorted(s) for p, s in paper_students.items()},
        student_papers=dict(student_papers),
        shared_papers=shared,
    )

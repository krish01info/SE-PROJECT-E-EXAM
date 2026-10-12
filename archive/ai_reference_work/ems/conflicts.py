"""M3 — Conflict Analysis (C3, MoSCoW R6).

* Paper conflict graph: papers p and q are joined iff at least one student is
  registered for both. Built from registrations, never from cohort labels, so
  electives and cross-cohort open courses are handled correctly (Plan §4.1).
* Teacher–student exclusion: teacher t taught paper p to section s, so t may
  not invigilate a room where a student of s is writing p.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from .mapping import PaperMap
from .model import Dataset


@dataclass
class ConflictGraph:
    adj: dict[str, set[str]]
    shared: dict[tuple[str, str], int]  # (p, q) sorted -> number of common students
    # exclusion relation
    taught: set[tuple[str, str, str]]  # (teacher, paper, section)
    teacher_papers: dict[str, set[str]]
    paper_teachers: dict[str, set[str]]

    def edges(self) -> list[tuple[str, str]]:
        return sorted(self.shared)

    def conflicts(self, p: str, q: str) -> bool:
        return q in self.adj.get(p, ())

    def max_clique(self) -> list[str]:
        """Largest clique found by greedy search from every vertex.

        A clique of c pairwise-conflicting papers needs (c-1)*gap+1 exam days,
        which gives the pre-solve check (C7) a strong lower bound.
        """
        best: list[str] = []
        for start in sorted(self.adj, key=lambda p: -len(self.adj[p])):
            clique = [start]
            cands = sorted(self.adj[start], key=lambda p: -len(self.adj[p]))
            for c in cands:
                if all(c in self.adj[x] for x in clique):
                    clique.append(c)
            if len(clique) > len(best):
                best = clique
        return sorted(best)


def build_conflicts(ds: Dataset, pm: PaperMap) -> ConflictGraph:
    adj: dict[str, set[str]] = {p: set() for p in pm.paper_students}
    shared: dict[tuple[str, str], int] = defaultdict(int)
    for sid, papers in pm.student_papers.items():
        for p, q in combinations(sorted(papers), 2):
            adj[p].add(q)
            adj[q].add(p)
            shared[(p, q)] += 1

    taught = set()
    teacher_papers: dict[str, set[str]] = defaultdict(set)
    paper_teachers: dict[str, set[str]] = defaultdict(set)
    for tid, code, sec in ds.teaching:
        pid = pm.code_to_paper[code]
        taught.add((tid, pid, sec))
        teacher_papers[tid].add(pid)
        paper_teachers[pid].add(tid)
    return ConflictGraph(adj, dict(shared), taught, dict(teacher_papers), dict(paper_teachers))

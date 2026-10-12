# EMS — Design and Implementation Notes

This document connects the Phase 0 Plan, the SRS v0.1, the MoSCoW prioritisation and the Design Lab diagrams
(all in this folder) to the code. Read it alongside them.

## 1. Architecture

The code follows the module table of SRS §2.1 one-to-one:

| Module | File | Feature | Notes |
|---|---|---|---|
| M1 Data Ingestion & Validation | `ems/ingest.py` | C1 | Every error carries **file, row and rule** (MoSCoW R2). The dataset is rejected if any error exists. |
| M2 Paper Mapping | `ems/mapping.py` | C2 | Course code → canonical paper, many-to-one. Everything downstream sees papers only. |
| M3 Conflict Analysis | `ems/conflicts.py` | C3 | Conflict graph from registrations, plus the teacher–(paper, section) exclusion relation. |
| M4 Scheduling Engine | `ems/scheduling.py` | C4 | CP-SAT model, see §2.2. |
| M5 Seating Engine | `ems/seating.py`, `ems/geometry.py` | C5 | Stripes and room sides, see §2.3. |
| M6 Duty Engine | `ems/duties.py` | C6 | CP-SAT model, see §2.4. |
| M7 Feasibility & Diagnostics | `ems/feasibility.py` + `diagnose_*` in M4/M6 | C7, C8 | Cross-cutting, as the plan requires. |
| M8 Override Manager | pins in `ingest.py`, `cli.py pin/unpin`, enforced in M4/M6 | C9 | Pins live in `pins.csv` (data store D7). |
| M9 Report Generator | `ems/reports.py` | C10 | Pure formatting, no solving. |
| EMS Controller | `ems/pipeline.py` | — | The `:EMS Controller` lifeline of the sequence diagram. |
| Exam Plan object | `ems/plan.py` | — | The state transition diagram, enforced. |
| Verifier | `ems/verify.py` | SRS 3.5 | Independent re-check of every hard rule from the output CSVs. |

The data stores of the Level-1 DFD map to files: D1 = the input CSVs, D2 = `course_codes.csv`, D3 is built in
memory each run, D4 = `schedule.csv`, D5 = `seating.csv`, D6 = `duties.csv`, D7 = `pins.csv`.

## 2. Algorithms

### 2.1 Vocabulary

The code uses the plan's vocabulary exactly: *cohort*, *section*, *paper*, *course code*, *slot* (date ×
session), *stripe*, *duty*. Roll numbers are the only student identifiers, and teacher IDs the only teacher
identifiers. Names never enter the system (SRS 3.1).

### 2.2 Scheduling (C4)

Variables: `y[p, t]` = paper *p* is in slot *t*; `sideA[p]` = paper *p* is seated on side A of every room.

Hard constraints:

* exactly one slot per paper. All of a paper's course codes share it automatically, because the model only
  knows papers.
* **gap rule** (Plan §4.2): for every conflict edge (p, q) and day d, `day[p,d] + Σ day[q,d'] ≤ 1` over
  `|d − d'| < min_day_gap`. The morning/evening wording in the original rule reduces to this one rule about
  days, as the plan proves.
* **seating feasibility**: per slot, Σ students on side A ≤ side-A seats of the usable rooms, and the same for
  side B. This is the exact form of the plan's "no paper takes more than about half the seats" condition (§2.3).
* pinned paper→slot overrides.

Objective, solved in two passes:

1. minimise the last exam day used (the span);
2. with the span fixed, minimise the rooms needed (`10 000 × Σ rooms_t + peak load`).

**Deviation from the plan, with reason:** the plan solves *papers → days* and *days → sessions* as two
stages. Done in sequence, stage 1 can pick days that no morning/evening split can seat, which then needs a
feedback loop. One model with both decisions avoids that, and the two-pass objective still gives the plan's
priorities (short period first, then balance). The second pass minimises **rooms** rather than raw seat
balance, because every room costs two invigilators. On the dummy data the first version (balance only) needed
796 duties; minimising rooms cut that to 410 with the same 13-day span.

"Usable rooms per slot" = `min(#rooms, #invigilators ÷ 2)`, in priority order. The invigilator pool therefore
limits seating capacity from the start, instead of failing later at the duty stage.

### 2.3 Seating (C5) — stripes and sides

`geometry.py` builds each room as a grid of seat-columns × rows. Seats are adjacent if they are side by side
on a bench, side by side across an aisle (configurable), or directly in front/behind (configurable).

Stripes follow Plan §4.3, with one rule covering every case:

* front/back adjacency **on** → each seat-column becomes two interleaved half-depth stripes (odd/even rows).
  A 2-wide bench gives the plan's "sem 1, sem 3, sem 1" alternation.
* front/back adjacency **off** → each seat-column is one full-depth stripe. A 3-wide bench gives the left/right
  stripes.

Two stripes are adjacent if any of their seats are. The stripe graph of a grid is **bipartite**, so every room
splits into side A and side B, with no adjacency inside a side. The scheduler puts each paper of a slot on one
side, and the seating engine fills each side's papers in roll order, stripe by stripe, room by room. Two
neighbours are always on opposite sides, so they always write different papers. The rule holds **by
construction**, and `verify.py` re-checks it from the output anyway.

This also settles Plan open question 1: with front/back adjacency counted, S and M rooms are treated the same
way, and the half-capacity bound holds in both.

### 2.4 Duties (C6)

Variables `x[t, room, slot]` exist only where the teacher is eligible. A teacher who taught paper *p* to section
*s* gets no variable for any room holding a student of *s* writing *p*. This is the exclusion rule enforced by
construction.

Hard: exactly 2 per open room, at most 1 per teacher per slot, own-paper coverage, pins.
Soft: at most 1 duty per teacher per day (weight 1000), one in-domain + one out-of-domain invigilator per room
(weight 100). Fairness is solved in two passes:

1. minimise the highest **weighted load** (duties ÷ rank weight);
2. keep that ceiling and minimise soft penalties + (highest − lowest weighted load).

### 2.5 Feasibility (C7) and diagnosis (C8)

The pre-solve check uses bounds that are cheap to compute and **necessary**. If one fails, no plan exists, and
the report says exactly by how much:

* a student with *k* papers needs `(k−1)·gap + 1` exam days; a clique of *c* mutually conflicting papers needs
  `(c−1)·gap + 1`;
* the largest paper must fit on one side of the usable rooms (if not, the report gives the missing seats as
  rooms or invigilators);
* total seats and total duties against supply;
* pins that already break the gap rule against each other;
* teachers for whom the coverage rule is impossible (reported and exempted, see §3).

When CP-SAT proves a stage infeasible, the stage is re-solved with an **assumption literal per rule group**: one
per conflicting pair, per slot-side capacity, per pin, per room's staffing, per teacher's coverage. CP-SAT then
returns a subset of rules that cannot hold together, and a deletion filter shrinks it towards a minimal set.
That set is translated into plain language with example students. For example:

```
Infeasible at stage: scheduling
  - [BLOCKING] gap-rule: papers E1, P1, P2, SH must be ≥ 2 exam day(s) apart pairwise for shared students;
    conflicting pairs: E1–P1 (10 shared student(s), e.g. A101); … P1–SH (4 shared student(s), e.g. A100) …
  - [BLOCKING] pinned-override: pin paper P1 to 2026-03-02 Morning; pin paper P2 to 2026-03-05 Morning
```

### 2.6 Overrides (C9) and stability

`ems pin` validates a pin immediately and stores it in `pins.csv`. On a re-solve into the same output folder,
the previous schedule and roster are passed to CP-SAT as **hints**, so pinning one teacher does not reshuffle
the whole plan. `--fresh` disables hints.

### 2.7 Exam Plan state machine

`plan.py` encodes the transition table of Design Lab §4.3 verbatim. Any event not in the table raises an
error, so the code cannot seat before scheduling or approve before reporting. `ems approve` locks the plan,
and `solve` then refuses to overwrite it without `--force`. Every transition is logged with a timestamp in
`plan_state.json`, and `ems status` prints the log.

## 3. Decisions on the Phase 0 open questions

| # | Question (Plan §12 / SRS 3.6) | Decision in code | Config key |
|---|---|---|---|
| 1 | Does front-to-back adjacency count? | **Yes.** MoSCoW R5 says "same row or column". It makes S and M rooms consistent and keeps the half-capacity bound true. | `seating.front_back_adjacent` |
| 2 | May same-cohort students writing different electives sit adjacent? | **Yes.** Conflicts are registration-based (Plan §4.1). Different electives are different papers. | — (structural) |
| 3 | Are "one duty on your own paper" and rank weights settled? | Implemented as specified, with weights configurable. A teacher who teaches *every* section of all their papers cannot satisfy the rule without breaking the exclusion rule, so they are **exempted and listed** instead of making the whole plan infeasible. | `duties.require_own_paper_duty`, `duties.rank_weights` |
| 4 | Is the ~4-papers-per-room cap real? | Kept **soft and only reported**. The side-based fill naturally gives ≤ 3 papers per room on all datasets. | `seating.max_papers_per_room_soft` |
| — | Is the gap measured in calendar or exam days? | Exam days (weekends and holidays skipped), matching the plan's "day number d". | `scheduling.min_day_gap` |

PhD scholars are weighted lower (0.5), as the plan states. Non-teaching invigilation-only **staff** (needed
for the real mid-term data) are a fifth rank with the same treatment.

## 4. Requirement traceability

| Requirement | Priority | Where | Test |
|---|---|---|---|
| R1 Dummy dataset | Must | `tools/generate_dummy.py` (base + realistic variant) | full runs in README |
| R2 Ingestion & validation | Must | `ingest.py` | `test_validation_*` |
| R3 Course code → paper mapping | Must | `mapping.py` | `test_many_codes_map_to_one_paper`, `test_shared_paper_sits_in_one_slot` |
| R4 Session separation | Must | `scheduling.py` | verifier H3 |
| R5 Adjacent seating | Must | `geometry.py`, `seating.py` | `test_sides_have_no_internal_adjacency`, `test_verifier_catches_adjacency_violation` |
| R6 Conflict graph & exclusion | Must | `conflicts.py` | `test_conflict_graph_is_registration_based` |
| R7 Invigilator assignment | Must | `duties.py` | verifier H7–H9 |
| R8 Pre-solve feasibility | Should | `feasibility.py` | `test_presolve_flags_*` |
| R9 Failure diagnosis | Should | `diagnose_schedule`, `diagnose_duties`, seating findings | `test_schedule_infeasibility_names_the_rules`, `test_teacher_pin_into_own_class_is_rejected` |
| R10 Manual pinning | Must | `cli.py pin`, M4/M6 | `test_paper_pin_is_honoured` |
| R11 Printed artefacts | Should | `reports.py` | `test_full_pipeline_passes_every_hard_rule` |
| R12 CSV relational bridge | Could | all inputs/outputs are relational CSV | — |
| R13 Fair assignment | Should | `duties.py` two-pass fairness | `fairness.csv`, verifier soft measures |
| R14 Teacher duty rosters | Must | `teacher_rosters.csv/.html` | ✓ |
| R15 Student timetable | Must | `student_timetables.csv/.html` | ✓ |
| R16 HoD approval & evidence | Could | `summary.html`, `ems approve` | `test_approval_locks_the_plan` |
| R17 Terminal-based, fixed I/O | Must | `python -m ems …` | — |
| R18 Issue tickets | Won't | not implemented, as agreed | — |

## 5. Known limits

* Solve times: about 2 minutes for the 1 200-student dummy dataset and under 1 minute for the mid-term data,
  on 2 CPU cores. Raise `time_limit_s` for larger data. The duty stage dominates.
* Rooms open in one flat priority order, with no building or proximity model (A1/A2 deferred, as planned).
* Teacher availability, special-needs seating and reserve pools remain out of scope (Plan §11.3).

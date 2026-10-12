# Exam Management System (EMS)

**Automated exam scheduling, seating allocation and invigilation duty assignment.**
Software Engineering project, BML Munjal University, 2026.

Harsh Vardhan (240467) · Himank Swami (240474) · Ishan Batra (240485) · Koushik Araveti (240512) · Krish Sharma (240514)

---

Every semester the examination cell has to produce three things by hand: an **exam schedule**, a **seating
plan** for every student, and an **invigilation duty roster**. EMS produces all three from plain CSV files, as
one solver pipeline:

```
 CSV inputs ─► M1 validate ─► M2 map course codes → papers ─► M3 conflict graph
                                                                   │
                         M7 pre-solve feasibility check ◄──────────┘
                                   │ (stops here with the exact deficit if no plan can exist)
                                   ▼
            M4 schedule ─► M5 seating ─► M6 duties ─► M9 reports + independent verifier
                 ▲              ▲             ▲
                 └──── M8 pinned overrides ───┘        M7 diagnoses any stage that fails
```

The design follows the team's documents in [`docs/`](docs): the Phase 0 Plan, the SRS v0.1, the MoSCoW
prioritisation and the Design Lab diagrams. [`docs/DESIGN.md`](docs/DESIGN.md) maps every module, decision and
requirement to the code.

## Results

| Dataset | Students | Papers | Exam days | Slots | Room-slots | Duties | Hard rules |
|---|---|---|---|---|---|---|---|
| Dummy (Plan §9) | 1 200 | 31 | **13** (optimal lower bound) | 13 | 204 | 408 | **11/11 pass** |
| Dummy — realistic variant¹ | 1 200 | 31 (33 codes) | **15** (lower bound) | 12 | 205 | 410 | **11/11 pass** |
| Mid-term March 2026 (real sheet)² | 1 502 | 18 | 5 | 6 | 166 | 332 | **11/11 pass** |

¹ Closes the gaps listed in Plan §11.2: one paper under two course codes, repeat students, and an open course
crossing cohorts.
² Reconstructed from the exam cell's master sheet. Compared with the manual plan in that sheet, EMS removes all
**167 same-day double exams** and cuts the peak from **56 rooms / 112 invigilators** to **33 / 66**. See
[`docs/CASE_STUDY_MIDTERM_2026.md`](docs/CASE_STUDY_MIDTERM_2026.md).

Generated plans are committed in [`out/`](out). Open `out/<dataset>/reports/index.html` in a browser.

## Quick start

```bash
pip install -r requirements.txt           # Python ≥ 3.10; the only dependency is Google OR-Tools

python -m ems validate data/dummy         # C1/C2: check inputs, show code→paper mapping
python -m ems check    data/dummy         # C7:  pre-solve feasibility check
python -m ems solve    data/dummy -o out/dummy      # full pipeline, ~2 min
python -m ems verify   out/dummy          # independent re-check of every hard rule
```

Then open `out/dummy/reports/index.html`.

### All commands

| Command | What it does |
|---|---|
| `validate DATA` | Load and validate inputs; every error names its file, row and rule |
| `check DATA [--set k=v]` | Pre-solve feasibility check (necessary conditions, exact deficits) |
| `solve DATA [-o OUT] [--pins F] [--set k=v] [--fresh]` | Run the pipeline; write CSVs, printable reports, verification |
| `verify OUT` | Re-check all hard rules from the output files alone |
| `pin DATA paper P --date D --session S` | Pin a paper to a slot (C9) |
| `pin DATA teacher T --room R --date D --session S` | Pin a teacher to a room (C9) |
| `pins DATA` / `unpin DATA N` | List / remove pins |
| `approve OUT` / `request-changes OUT` / `close OUT` | HoD actions on the Exam Plan state machine |
| `status OUT` | Current plan state and its full transition history |

`--set` changes any policy for one run without editing files, e.g.
`--set scheduling.min_day_gap=1 --set seating.front_back_adjacent=false`.

### Datasets

```bash
python tools/generate_dummy.py                       # data/dummy           (Plan §9 exactly)
python tools/generate_dummy.py --variant realistic   # data/dummy_realistic (closes §11.2 gaps)
python tools/import_midterm.py data/raw/Mid_Term_Data_March_2026.csv   # data/midterm_2026
python tools/compare_manual.py data/midterm_2026 out/midterm_2026      # manual plan vs EMS
```

The raw mid-term sheet and the pseudonym→name map live in `data/raw/`, which is **git-ignored**. Following
SRS §3.1, only identifiers are stored; names and internal discussion notes never enter the repository.

## Inputs (one folder per dataset)

All inputs are relational CSV tables, so moving to a database later is mechanical (MoSCoW R12).

| File | Columns | Notes |
|---|---|---|
| `config.json` | calendar, gap rule, adjacency, duty policy, solver limits | every open policy question is a setting |
| `sections.csv` | `section_id, cohort_id` | |
| `students/<section_id>.csv` | `student_id` | one roster per section; roll order = sort order |
| `teachers.csv` | `teacher_id, rank, department` | rank ∈ professor, associate, assistant, phd, staff |
| `papers.csv` | `paper_id, title, department` | the thing actually examined |
| `course_codes.csv` | `course_code, paper_id, cohort_id` | **many codes → one paper** |
| `registrations.csv` | `student_id, course_code` | |
| `teaching.csv` | `teacher_id, course_code, section_id` | drives the exclusion and coverage rules |
| `rooms.csv` | `room_id, building, bench_cols, rows, seats_per_bench, priority` | seats_per_bench 1 (2-wide bench) or 2 (3-wide) |
| `pins.csv` *(optional)* | `kind, paper_id, teacher_id, room_id, date, session` | manual overrides |

## Outputs

| File | For whom |
|---|---|
| `schedule.csv`, `seating.csv`, `duties.csv` | the plan itself (data stores D4–D6) |
| `student_timetables.csv`, `reports/student_timetables.html` | students — searchable by roll number |
| `teacher_rosters.csv`, `reports/teacher_rosters.html` | teachers and invigilators |
| `reports/slot_<date>_<session>.html` | invigilators on duty — per room: **seating chart, door list, attendance sheet grouped by paper** (one room per printed page) |
| `slot_summary.csv`, `fairness.csv`, `reports/summary.html` | exam cell and HoD — per-slot summary, utilisation, fairness evidence, verification |
| `feasibility_report.txt`, `diagnosis.txt` | why a plan is or isn't possible |
| `verification.txt/.json` | the independent re-check of every hard rule |
| `plan_state.json` | the Exam Plan's state and transition history |

## The rules

| Area | Rule | Type | How it is guaranteed |
|---|---|---|---|
| Scheduling | No student writes on exam days less than `min_day_gap` apart | Hard | CP-SAT constraint on every conflict edge |
| Scheduling | All course codes of one paper share one slot | Hard | the solver only knows papers |
| Scheduling | Seats fit with neighbours separated (≈ half-capacity rule) | Hard | per-slot side capacity |
| Scheduling | Shortest exam period, then fewest rooms | Objective | two-pass optimisation |
| Seating | No two adjacent students write the same paper | Hard | bipartite room sides, by construction |
| Seating | Rosters laid out in roll order across stripes | Hard | fill order |
| Seating | ≤ ~4 papers per room | Soft | reported (all runs ≤ 3) |
| Duties | Exactly 2 invigilators per open room; ≤ 1 duty per teacher per slot | Hard | CP-SAT |
| Duties | Never invigilate a room holding a student you taught for that paper | Hard | ineligible variables never exist |
| Duties | Every teacher (not PhD/staff) gets ≥ 1 duty on a paper they teach | Hard | CP-SAT; impossible cases exempted and listed |
| Duties | Rank-weighted fairness; ≤ 1 duty per day; in/out-of-domain pair | Soft | two-pass optimisation |

How the open questions in Plan §12 were decided is in [`docs/DESIGN.md` §3](docs/DESIGN.md#3-decisions-on-the-phase-0-open-questions).
In short: front-to-back adjacency counts (MoSCoW R5), different electives may sit together, duty weights are
configurable, and the 4-paper cap stays soft.

## Repository layout

```
ems/            the system (one file per SRS module; see docs/DESIGN.md)
tools/          dataset generator, mid-term importer, manual-vs-EMS comparison
tests/          pytest suite (21 tests, ~15 s): python -m pytest
data/           datasets: dummy, dummy_realistic, midterm_2026  (data/raw is git-ignored)
out/            generated plans and printable reports for each dataset
docs/           Phase 0 plan, SRS, MoSCoW, design-lab diagrams, DESIGN.md, case study
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests cover validation errors (file/row/rule), the many-codes-one-paper mapping, registration-based
conflicts, stripe and side geometry, feasibility bounds, the full pipeline, pins, scheduling and duty
diagnoses, and the state machine. They also include a **tamper test**: a seating file is edited so two
neighbours share a paper, and the verifier must catch it.

## Disclosure

As stated in the Phase 0 Plan and SRS, the team used Claude (Anthropic) during the project. The implementation
in this repository was written with Claude's help from the team's own plan, SRS, prioritisation and design
diagrams.

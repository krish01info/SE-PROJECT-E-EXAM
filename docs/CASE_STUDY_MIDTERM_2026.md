# Case study: the March 2026 mid-term exams

The Phase 0 plan lists as a limitation that *"no live institutional data has been obtained"*. The exam cell's
mid-term master sheet for 23–27 March 2026 is live data. This case study runs EMS on it and compares the
result with the plan the sheet records.

## 1. From sheet to dataset

The sheet is a course list, not a registration export. Each row has a course, the teacher of each section
column (CSE1–CSE8, ME, ECOMP), a batch year, a date/session and a student count. There are no roll numbers.
`tools/import_midterm.py` therefore **reconstructs** a dataset and records every assumption in
`data/midterm_2026/import_report.md`. Key points:

* 3 cohorts (2025, 2024, 2023 batches), 28 sections, **1 502 students, 18 papers, 4 486 paper-sittings**.
  Every course count in the sheet is reproduced exactly.
* Section sizes are estimated so every course's count fits its offering sections.
* Courses the manual plan put in the same slot for the same batch are treated as **alternative electives**
  (Discrete Maths / Numerical Methods, Deep Learning / Blockchain, and the two small ME/ECOM papers).
* MEC1101 (a practical in GA 102) and CSE2021 (lab exam run by the coordinator) are excluded, as the sheet's own
  discussion decided.
* 42 faculty and 7 staff are named in the sheet. They are pseudonymised, and the name map is kept in the
  git-ignored `data/raw/`.
* Rooms are not in the sheet. The sheet's stated room size (30 seats) is used for 36 assumed rooms;
  **replace `rooms.csv` with the real room list** before relying on room counts.

Re-run it with:

```bash
python tools/import_midterm.py data/raw/Mid_Term_Data_March_2026.csv
python -m ems check data/midterm_2026
python -m ems solve data/midterm_2026 -o out/midterm_2026
python tools/compare_manual.py data/midterm_2026 out/midterm_2026
```

## 2. What the feasibility check found

**The project's default gap rule cannot fit a 5-day window.** With `min_day_gap = 2`, a 3rd-year student writing
5 papers needs 9 exam days:

```
[BLOCKING] student-day-bound: the busiest student writes 5 papers, needing ≥ 9 exam days at gap 2;
           calendar has 5. 528 student(s) cannot fit. Fix: extend the calendar by ≥ 4 exam day(s),
           or lower min_day_gap (with gap 1 they need 5 day(s))
```

The mid-term dataset therefore uses `min_day_gap = 1` (no student writes two papers on one day). That is also
what the exam cell was aiming for.

**The named people cannot staff the rooms.** If only the 49 people named in the sheet invigilate, at most
24 rooms can open per slot. A 485-student paper, with neighbours separated, needs 33 rooms:

```
[BLOCKING] paper-too-large: paper MTH2801 has 485 students but one slot can seat at most 360 students
           of a single paper; short by 125 seat(s) — needs 18 more invigilator(s)
```

The sheet reaches the same conclusion ("+6 from outside", "+3 from outside"). The importer therefore adds a
pool of 20 outside invigilators; re-import with `--extra-invigilators 0` to reproduce the shortfall. EMS
reports this before any solving, with the exact number of people missing.

## 3. Manual plan vs EMS

Both plans are measured on the same reconstructed registrations, with 30-seat rooms and no two neighbours
writing the same paper (`out/midterm_2026/manual_vs_ems.md`):

| Measure | Manual plan (sheet) | EMS |
|---|---|---|
| Students with two papers in the same slot | 0 | 0 |
| **Students with two papers on the same day** | **167** | **0** |
| Students with papers on consecutive days | 999 | 1 360 |
| Slots used | 8 | 6 |
| Room-slots needed | 193 | 166 |
| **Peak rooms in one slot** | **56** | **33** |
| Invigilation duties | 386 | 332 |
| **Peak invigilators in one slot** | **112** | **66** |

What this means:

* **Same-day exams.** The sheet puts *Joy of Engineering* (all 485 first-years) on Wednesday morning and
  *Science, Technology & Public Policy* (180 first-years) on Wednesday afternoon. Every PSP student
  therefore writes twice that day. EMS never does this.
* **Room crunch.** The sheet's Wednesday morning has three large papers (JoE 485, DCCN 430, Logical Reasoning
  409). Seating 1 324 students with neighbours separated needs about 56 rooms. That matches the "room shortage"
  the exam cell discussed in the sheet. EMS spreads the large papers so no slot needs more than 33 rooms and 66
  invigilators.
* **Trade-off.** EMS packs papers into fewer slots, so more students write on consecutive days. The gap-1 rule
  allows this. If consecutive days should be avoided, set `min_day_gap = 2` and lengthen the window (≥ 9 exam
  days for 3rd-years).
* The CSV is the *Master Sheet* as exported. The discussion notes mention a later edit (*Master Sheet Ed.*)
  that moved most 2023-batch papers to the afternoon, which would ease the Wednesday crunch. Those edits are
  not in this file, so the comparison is against the exported version.

## 4. Verification

All eleven hard rules pass on the EMS plan, including the exclusion rule. Every one of the 38 eligible teaching
staff gets a duty on a paper they teach. Four teachers teach every section of their paper, so the rule is
impossible for them; they are exempted and listed (e.g. the sole teacher of *Science, Technology & Public
Policy*). See `out/midterm_2026/verification.txt`.

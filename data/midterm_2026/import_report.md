# Import report — Mid-term March 2026 master sheet

This dataset is **reconstructed**. The sheet lists courses, per-section teachers and per-course student counts but no roll numbers, so rosters and registrations are synthesised as described in `tools/import_midterm.py`. Treat results as a realistic case study, not as the official plan.

* 28 sections in 3 cohorts, 1502 students
* 18 papers, 4486 registrations
* 42 faculty and 7 invigilation-only staff named in the sheet (pseudonymised; name map kept outside the dataset), plus **20 outside invigilators** (X01…) — the sheet itself relies on "+6 from outside" / "+3 from outside", and the named people alone can staff only ~24 rooms. Re-import with `--extra-invigilators 0` to see `ems check` report that shortfall
* 15 reconstructed student(s) received no paper and were dropped
* 36 assumed rooms of 30 seats (3 bench columns × 5 rows × 2 seats) — **replace rooms.csv with the real room list**
* Calendar 23–27 March 2026, Morning/Afternoon. `min_day_gap` = 1 (no student sits two papers on one day). The project's default rule (gap 2) cannot fit this 5-day window; `ems check` shows why.

## Decisions taken

* **MEC1101 Elements of Mechanical Engineering** excluded — practical exam in GA 102 over Thu/Fri with no student count — scheduled outside the written-exam plan.
* **CSE2021 Database Management System** excluded — lab-based exam; coordinator runs it in NB labs on Tuesday (sheet discussion item 3).
* **FIN1001 Financial Markets: From Fundamentals to AI-Driven Analytics** is multidisciplinary; its 42 takers are drawn from Y2-2024 (assumption).
* Same-cohort courses the manual plan put in one slot are treated as alternative electives: CSE3726 / CSE4007; ECE2705 / MEC2025; MTH1802 / MTH1803.

## Section sizes (estimated)

| Section | Cohort | Students |
|---|---|---|
| 2025-CSE1 | Y1-2025 | 64 |
| 2025-CSE2 | Y1-2025 | 64 |
| 2025-CSE3 | Y1-2025 | 64 |
| 2025-CSE4 | Y1-2025 | 64 |
| 2025-CSE5 | Y1-2025 | 53 |
| 2025-CSE6 | Y1-2025 | 54 |
| 2025-CSE7 | Y1-2025 | 54 |
| 2025-ECOMP | Y1-2025 | 54 |
| 2025-ME | Y1-2025 | 54 |
| 2024-CSE1 | Y2-2024 | 48 |
| 2024-CSE2 | Y2-2024 | 48 |
| 2024-CSE3 | Y2-2024 | 48 |
| 2024-CSE4 | Y2-2024 | 48 |
| 2024-CSE5 | Y2-2024 | 48 |
| 2024-CSE6 | Y2-2024 | 48 |
| 2024-CSE7 | Y2-2024 | 48 |
| 2024-CSE8 | Y2-2024 | 48 |
| 2024-ECOMP | Y2-2024 | 48 |
| 2024-ME | Y2-2024 | 12 |
| 2023-CSE1 | Y3-2023 | 66 |
| 2023-CSE2 | Y3-2023 | 59 |
| 2023-CSE3 | Y3-2023 | 66 |
| 2023-CSE4 | Y3-2023 | 66 |
| 2023-CSE5 | Y3-2023 | 66 |
| 2023-CSE6 | Y3-2023 | 66 |
| 2023-CSE7 | Y3-2023 | 66 |
| 2023-CSE8 | Y3-2023 | 43 |
| 2023-ME | Y3-2023 | 35 |

## Course counts: sheet vs reconstructed

| Course | Sheet | Reconstructed | Note |
|---|---|---|---|
| CSE2029 | 430 | 430 | ok |
| CSE3702 | 409 | 409 | ok |
| CSE3703 | 395 | 395 | ok |
| CSE3722 | 394 | 394 | ok |
| CSE3726 | 44 | 44 | ok |
| CSE4007 | 185 | 185 | ok |
| ECE1101 | 255 | 255 | ok |
| ECE2016 | 17 | 17 | ok |
| ECE2705 | 17 | 17 | ok |
| FIN1001 | 42 | 42 | ok |
| MEC2025 | 12 | 12 | ok |
| MTH1802 | 57 | 57 | ok |
| MTH1803 | 244 | 244 | ok |
| MTH2801 | 485 | 485 | ok |
| PRJ1101 | 485 | 485 | ok |
| PSP1805 | 180 | 180 | ok |
| PSP4706 | 409 | 409 | ok |
| SKL2711 | 426 | 426 | ok |

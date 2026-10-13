# Data design spec

The rules prototype1's input data must follow. The team chooses the numbers, and each choice needs a reason.

The labels mean the same as in `prototype1_model_spec.md`: **Decided**, **Default** and **Open**.

---

## 1. Purpose

The dataset is the test. If it is easy, any tool passes and we learn nothing.

- It should look like what the exam cell actually deals with: one big program, shared papers, tight rooms, too few teachers.
- It should stay small enough to reason about.
- Designing it is the hard part of prototype1, and it is the team's job.

## 2. Files and columns

**Decided (Phase 0):** CSV files, one roster file per section, and identifiers only, with no names.

**Default:** the columns below.

| File | Columns | Example row |
|---|---|---|
| `sections.csv` | `section_id, cohort_id, program, year` | `BT2_I, BT2, BTECH, 2` |
| `sections/<section_id>.csv` | `student_id` | `BT2S0001` |
| `courses.csv` | `course_code, title, cohort_id, kind` | `MTH2001, Discrete Mathematics, BT2, CORE` |
| `registrations.csv` | `student_id, course_code` | `BT2S0001, MTH2001` |
| `rooms.csv` | `room_id, type, rows, seat_columns` | `M01, M, 7, 6` |
| `teachers.csv` | `teacher_id, rank` | `T001, ASST` |
| `teaching.csv` | `teacher_id, course_code, section_id` | `T001, MTH2001, BT2_I` |

- `kind` is `CORE` or `ELECTIVE`.
- `rank` is one of `PROF`, `ASSOC`, `ASST` or `PHD`.
- `type` is `S` or `M`, with the sizes in `prototype1_model_spec.md` §9.
- A course code belongs to one cohort. When cohorts share a paper, each cohort has its own code, and the codes are grouped under `same_paper` in `constraints.yaml`.
- `registrations.csv` is the source of truth for who writes what.
- **Default ID formats:**
  - students `BT2S0001`
  - sections `BT2_I`, `BT2_II`, …
  - rooms `S01`, `M01`
  - teachers `T001`
  - course codes look real (`MTH2001`, `CSE2003`), so that shared papers show up as different codes, as they do at the university.

`settings.yaml` and `constraints.yaml` are described in `prototype1_model_spec.md` §6–7.

## 3. Checks

The tool rejects input that breaks any of these. Each error names the file, the row and the rule. For example:

```
registrations.csv row 214: course code CSE9999 is not in courses.csv
```

**Every file:**

- all files are present, and their headers match §2
- IDs are unique within their file and never blank
- every ID used refers to a row that exists

**Students and registrations:**

- every student appears in exactly one section file
- every student has at least one registration, with no duplicate rows
- **Default:** a student registers only for course codes of their own cohort. This check is how prototype1 keeps out repeat students and multidisciplinary courses, which are out of scope (Decided).
- every course code has at least one registration

**Rooms, teachers and teaching:**

- room `type` is `S` or `M`; `rows` and `seat_columns` are positive whole numbers
- teacher `rank` is one of the four values
- in `teaching.csv`, the course code is offered to that section's cohort, and at least one student of that section is registered for it

**Settings and constraints:**

- `settings.yaml`: dates are valid, `start_date` is on or before `end_date`, there are exactly two sessions, and `min_gap_days` and `invigilators_per_room` are whole numbers of at least 1
- `constraints.yaml`: every code exists, each group has at least two codes, and a code appears in at most one `same_paper` group

## 4. What the data must contain

Each feature is there to test something.

| Feature | What it tests | Label |
|---|---|---|
| One paper shared by two cohorts under different codes, listed in `same_paper` | Same paper under different codes. It also links the cohorts' schedules, so scheduling stops being trivial. | Decided |
| S and M rooms | Both room shapes | Decided |
| BTech much larger than the other programs | One program dominating seat demand | Default |
| Electives of uneven size | Room packing | Default |
| Seats tight enough that the busiest slots need mixed rooms | One paper per room against mixing | Default |
| An exam window tight enough for the gap rule to matter, with a weekend and a holiday inside it | The gap rule, including Friday then Monday | Default |
| Teachers who teach in more than one cohort, or the same paper to several sections | "Own paper, but not own class" | Default |
| PhD scholars who teach nothing | The PhD exemption | Default |
| More `ASST` than `ASSOC` than `PROF` | A realistic teacher body | Default |
| A teacher pool tight enough that duties can run short | The duty shortage message | Default |

**Not in prototype1 (Decided):** repeat students, multidisciplinary and open courses, names and buildings.

## 5. Datasets

**Default.**

| Name | What it is |
|---|---|
| `tiny` | Small enough to solve by hand, e.g. two cohorts, a few students per section, three rooms, one week. The team writes down the expected plan before running the tool. |
| `main` | The realistic one, built from §4 and §6. |
| `impossible_days`, `impossible_seats`, `impossible_teachers` | Each breaks one thing on purpose, to trigger one no-plan reason. |

## 6. Numbers to decide (Open)

Answer each question with a reason in §8.

1. Which programs and cohorts are there? How many sections does each have, and how many students per section?
2. How many core papers and electives does each cohort have? How large is each elective?
3. Which papers are shared across cohorts, and under which codes?
4. How many S rooms and M rooms are there? How do the seats compare with the busiest slot?
5. How many teachers are there, and how many of them are PhD scholars? How many sections can one teacher teach?
6. How long is the exam window? Which weekend and which holiday fall inside it?
7. What makes `main` hard? And what would show the tool is good, not just valid?

**Starting point.** The Phase 0 dummy data is in `archive/initial_dir/`: 1200 students in four cohorts, 31 papers, 57 teachers, 40 rooms and 20 days. Its known weaknesses:

- no two cohorts share a paper, so scheduling is trivial
- every code is its own paper
- the ranks are top-heavy

**Room capacity under the column rule:**

- with one paper in a room, an S room holds 12 and an M room holds 21
- with two papers mixed, an S room holds 18 and an M room holds 42

## 7. Generator rules

- **Decided (Phase 0):** a Python script generates the data and can be re-run with different parameters.
- **Decided:** the data is made up. It contains no real names, roll numbers, IDs, phone numbers or emails. Real files may inspire the structure, such as room sizes or cohort sizes, but no rows are copied from them.
- **Default:** the same parameters and seed always give identical files.
- **Default:** the parameters sit at the top of the script.
- **Default:** the script writes a complete input folder, including `settings.yaml` and `constraints.yaml`.
- **Default:** the script may work from a compact form, such as cohort cores plus one elective per student, and expand it into `registrations.csv`. The tool reads only `registrations.csv`.
- **Default:** after writing, the script runs the checks in §3.

## 8. Team decisions

| Date | Question | Decision | Reason |
|---|---|---|---|
| 2026-10-13 | Q1 Programs, cohorts | Keep the Phase 0 cohorts: BT2 and BT3 (9 sections each), BB2 and BB3 (3 sections each). 1,200 students. | It already has different programs and different years, and BTech dominates. |
| 2026-10-13 | Q1 Section size | Every section has 50 students. | Keep it simple for prototype1. |
| 2026-10-13 | Q2 Papers per cohort | Each student writes all their cohort's cores plus one elective. Cores: BT2 6, BT3 6, BB2 3, BB3 4. Electives: BT2 250/110/90, BT3 240/115/95, BB2 55/55/40, BB3 50/50/50. | Uneven sizes would be more realistic, but for prototype1 BB3 stays at 50 each. BTech's electives are already uneven, so room packing is still tested. |
| 2026-10-13 | Q3 Shared paper | Discrete Maths is shared by BT2 and BT3 under different codes. In BT2 it stays an elective (250). In BT3 it replaces one core, so BT3 still writes 7 papers. Which BT3 core it replaces is chosen in step 2. | Discrete Maths is a real paper. Core in one year and elective in the other keeps the shared paper manageable (250 + 450 = 700 students, not 900). Replacing a core keeps BT3 at 7 papers, so the window stays the same. |
| 2026-10-13 | Q4 Rooms | 18 S rooms and 18 M rooms: 594 seats with one paper per room, 1,080 mixed. | We don't have unlimited rooms. The busiest slot only just fits. |
| 2026-10-13 | Q5 Teachers | About 85 teachers, 10 of them PhD scholars. The rest are 50% ASST, 30% ASSOC, 20% PROF. | 36 rooms × 2 invigilators = 72 teachers in the busiest slot, so we need more than 72. The rank split follows the spec's realistic-teacher-body default (§4). |
| 2026-10-13 | Q5 Sections per teacher | Each faculty member teaches 2–3 sections. Nobody teaches every section writing a paper, so every core and elective has at least 2 teachers split by section. 2 teachers teach Discrete Maths in both BT2 and BT3. | A teacher with every section of a paper can’t satisfy both duty rules (§10, Open). Cross-cohort teachers test “own paper, but not own class”. |
| 2026-10-13 | Q6 Exam window | Mon 2 Nov to Wed 18 Nov 2026, Mon–Fri, holiday Wed 11 Nov. | The window comes from the number of papers. 7 papers with a clear day between each need 2–16 Nov. A weekday holiday pushes that to 18 Nov. |
| 2026-10-13 | Q7 What makes `main` hard | Fitting every student's exams into the short window under the gap rule. | The window is set at the minimum. |
| 2026-10-13 | Q7 What makes a plan good | Fewer mixed rooms. | With mixed papers, invigilators have to sort the answer copies by paper before sending them to each teacher. |

# Exam planner (prototype 1)

Give it your university's exam data, and it makes the full exam plan:

1. **a date sheet:** which paper is on which day, morning or evening,
2. **a seating plan:** a picture of every room, showing who sits where,
3. **invigilation duties:** which two teachers sit in each room.

It follows every rule below, or it tells you why no plan is possible. It never hands you a plan that breaks a rule.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Try it in one minute](#2-try-it-in-one-minute)
3. [What you get](#3-what-you-get)
4. [Make your own data](#4-make-your-own-data)
5. [The rules every plan follows](#5-the-rules-every-plan-follows)
6. [When something goes wrong](#6-when-something-goes-wrong)
7. [Check a plan](#7-check-a-plan)
8. [Exit codes](#8-exit-codes)
9. [Datasets included](#9-datasets-included)
10. [Run the tests](#10-run-the-tests)
11. [How it works](#11-how-it-works)
12. [What it does not do yet](#12-what-it-does-not-do-yet)

---

## 1. What you need

- **Python 3.10 or newer**
- **PyYAML**, to read the two settings files:

  ```
  pip install pyyaml
  ```

- **pytest**, only if you want to run the tests (section 10):

  ```
  pip install pytest
  ```

Nothing else. There's no database and no internet, and no solver library.

## 2. Try it in one minute

Open a terminal in the `prototype1/` folder and run:

```
python main.py data/tiny
```

`data/tiny` is a small example: 16 students, 3 rooms, 9 teachers, one week. You should see:

```
Input OK: 2 sections, 16 students, 8 course codes (7 papers), 3 rooms, 9 teachers.
Scheduled 7 papers on 3 days, 2026-11-02 to 2026-11-06.
Fullest session: 2026-11-02 morning, 16 of 45 seats (29 left).
Seating: 7 room files (1 with two papers). Most rooms in one slot: 3 of 3 (2026-11-06 morning).
Duties: 14. Each regular teacher has 1 to 2; PhD scholars have 0. Teachers with both shifts on one day: 0 times.
Wrote output/2026-11-05_15-55-57
```

The plan is in the folder on the last line. On Windows the path shows with `\` (`output\2026-11-05_15-55-57`); both work in the commands below. Then check it (section 7):

```
python check.py data/tiny output/2026-11-05_15-55-57
```

```
Plan check: no problems. 7 papers, 7 room files, 48 seats, 14 duties checked.
```

For a realistic run, use `data/main`: 1,600 students, 56 papers, 36 rooms, 85 teachers.

```
python main.py data/main
```


## 3. What you get

Every run makes a new folder named by the time of the run, so old plans are never overwritten:

```
output/2026-11-05_15-55-57/
├── schedule.csv                          the date sheet
├── duties.csv                            who invigilates which room
└── daywise_seating_plans/
    └── 2026-11-02/
        └── morning/
            ├── S01.csv                   picture of room S01
            └── S02.csv
```

**`schedule.csv`** has one row per paper. Course codes that are one paper are joined with `;`.

```
date,session,paper_id,course_codes,students
2026-11-02,morning,CSE2001,CSE2001;CSE2003,16
2026-11-04,morning,CSE2002,CSE2002,8
```

**`duties.csv`** has one row per teacher per room.

```
date,session,room_id,teacher_id
2026-11-02,morning,S01,T001
2026-11-02,morning,S01,T003
```

**Room CSVs** are a picture of the room, as the invigilator at the front sees it. Row 1 is the front row and column 1 is on the left. Each cell is `paper:student`, and a blank cell is an empty seat. There is no header row. Open one in Excel or LibreOffice:

```
CSE2001:BT2CSE0001,,CSE2001:BT2CSE0007
CSE2001:BT2CSE0002,,CSE2001:BT2CSE0008
CSE2001:BT2CSE0003,,
CSE2001:BT2CSE0004,,
CSE2001:BT2CSE0005,,
CSE2001:BT2CSE0006,,
```

Here CSE2001 is in columns 1 and 3, with column 2 empty, so no two students of one paper sit side by side. Only rooms in use get a file.

## 4. Make your own data

Put your data in a folder of its own, for example `data/myuni/`, then run `python main.py data/myuni`. The tool checks everything first and lists every mistake (section 6), so you can fix them all in one go.

**Use IDs only, never names.** Don't put real names, phone numbers or emails in these files.

### The folder

```
data/myuni/
├── settings.yaml          dates, sessions, gap, invigilators per room
├── constraints.yaml       course codes that are one paper
├── sections.csv           one row per section
├── sections/              one file per section, listing its students
│   ├── BT2CSE_I.csv
│   └── BT2CSE_II.csv
├── courses.csv            one row per course code
├── registrations.csv      which student writes which course code
├── rooms.csv              one row per room
├── teachers.csv           one row per teacher
└── teaching.csv           which teacher teaches which course code to which section
```

All CSV files have a header row with exactly the columns below. Excel's "CSV UTF-8" format works.

### Words used here

| Word | Meaning | Example |
|---|---|---|
| Cohort | A program plus a year, e.g. BTech CSE 2nd year | `BT2CSE` |
| Section | Part of a cohort, about 50 students | `BT2CSE_I` |
| Course code | A course as offered to one cohort | `CSE2001` |
| Paper | One question paper, written in one sitting. Several course codes can be one paper. | `CSE2001` |
| Slot | A date plus a session | 2 Nov morning |

### `sections.csv`

```
section_id,cohort_id,program,year
BT2CSE_I,BT2CSE,BTECH,2
BT2CSE_II,BT2CSE,BTECH,2
```

Every section needs a file `sections/<section_id>.csv`.

### `sections/<section_id>.csv`

The students of one section, in roll order:

```
student_id
BT2CSE0001
BT2CSE0002
```

A student appears in exactly one section file.

### `courses.csv`

```
course_code,title,cohort_id,kind
CSE2001,Data Structures & Algorithms,BT2CSE,CORE
CSE2010,Quantum Computing,BT2CSE,ELECTIVE
```

- `kind` is `CORE` or `ELECTIVE`.
- A course code belongs to one cohort. If two cohorts write the same paper, give each cohort its own code and list the codes together in `constraints.yaml`.

### `registrations.csv`

Who writes what. This is the file the tool trusts for every seat.

```
student_id,course_code
BT2CSE0001,CSE2001
BT2CSE0001,CSE2010
```

- Every student has at least one row, and no row appears twice.
- A student writes only course codes of their own cohort.
- Every course code has at least one student.

### `rooms.csv`

```
room_id,type,rows,seat_columns
S01,S,6,3
M01,M,7,6
```

- `type` is `S` (small) or `M` (medium).
- `rows` and `seat_columns` are the room's size. A seat column is one line of seats from the front to the back.
- The tool picks the mix of room sizes that seats each session in the fewest rooms (then with the fewest empty seats). Among rooms of the same size it uses the ones higher up in this file first, so put the rooms you'd like used first at the top.

With one paper in a room, only every other column is used. So an S room (6 × 3) holds 12 students of one paper, and an M room (7 × 6) holds 21. Two papers in alternate columns fill it: 18 and 42.

### `teachers.csv`

```
teacher_id,rank
T001,PROF
T076,PHD
```

`rank` is `PROF`, `ASSOC`, `ASST` or `PHD`. PhD scholars are asked to invigilate only when nobody else is free, because research is their main work.

### `teaching.csv`

Which teacher teaches which course code to which section:

```
teacher_id,course_code,section_id
T001,CSE2001,BT2CSE_I
T002,CSE2001,BT2CSE_II
```

- The course code must be offered to that section's cohort.
- At least one student of that section must be registered for it.

This file matters for duties: a teacher never invigilates their own students (section 5).

### `settings.yaml`

```yaml
start_date: 2026-11-02            # first possible exam day
end_date: 2026-11-20              # last possible exam day
exam_weekdays: [Mon, Tue, Wed, Thu, Fri]
holidays: [2026-11-11]            # no exams; still count as gap days
sessions: [morning, evening]      # exactly two
min_gap_days: 2                   # days between one student's exams; 2 = one clear day
invigilators_per_room: 2
```

- Dates are `YYYY-MM-DD`, and `start_date` is on or before `end_date`.
- Weekdays are written `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun`.
- `holidays` can be empty: `holidays: []`.
- `min_gap_days` and `invigilators_per_room` are whole numbers, 1 or more.

### `constraints.yaml`

Course codes that are **one question paper**, written together in one sitting:

```yaml
same_paper:
  - [MTH2001, MTH3011]
  - [CSE3001, CSE3010, CSE4005]
```

- Each group has at least two codes, every code exists in `courses.csv`, and a code is in at most one group.
- The paper's ID is the group's first code.
- Leave it empty (`same_paper: []`) if there are none.
- You don't list clashes here. The tool works out from `registrations.csv` which papers share students.

## 5. The rules every plan follows

**Dates**

- Every paper gets exactly one slot, and all its students write it then.
- Exams only on exam days: inside the window, on an exam weekday, not a holiday.
- **Gap rule:** a student's two exams are at least `min_gap_days` apart. With 2, nobody has two exams on one day or on two days in a row. Friday then Monday is fine.
- Codes in one `same_paper` group are written in the same slot.

**Seats**

- Every student writing in a slot gets exactly one seat.
- **Column rule:** two students of the same paper never sit in side-by-side columns. Directly in front or behind is fine.
- One paper per room where possible. Two papers share a room only when rooms run out, and never three.
- Each session uses the fewest rooms it can: before seating, the tool tries the mixes of room sizes and picks the one with the fewest rooms, then the fewest empty seats. For example, 45 students get 1 M room and 2 S rooms (21 + 12 + 12, no empty seat), not 2 M rooms and an S room with 3 students in it.
- A paper's students sit in roll order (`student_id`), down each column, then left to right, room after room (rooms in the order of `rooms.csv`).

**Duties**

- Every room in use gets `invigilators_per_room` teachers.
- A teacher has at most one duty per slot.
- A teacher never invigilates a room holding a student they teach for the paper written there.
- A teacher (not a PhD scholar) invigilates each paper they teach at least once, in a room without their own students. If every room of their paper holds their students, they get a room with a different paper in the same slot, so they're nearby if the question paper has a mistake.
- Duties are spread out: a teacher with no other duty that day comes first, then the one with the fewest duties so far.

## 6. When something goes wrong

### Your data has mistakes

The tool lists **every** problem with its file, row and rule, writes nothing, and stops:

```
Input is invalid: 1 problem(s), 1 rule(s) broken.

[course code exists] 1 problem(s)
  registrations.csv row 3: course code CSE9999 is not in courses.csv
```

Fix the rows it names and run again. If a file is missing or unreadable, it reports that first, because the other checks need every file.

### No plan is possible

Sometimes the data is fine but no plan can follow every rule: too few rooms, too few teachers, or a window too short. The tool then makes a new output folder with **only** a file `why.txt`, which says which rule can't be met and gives the numbers:

```
No plan possible.
Rule: duties
Slot: 2026-11-06 morning
Every room needs 3 teachers. Short: M01 has 2.
Needs 9 teachers, 8 could be placed (8 regular teachers, 1 PhD scholars; nobody sits with their own students or has two duties in one slot).
```

What you can change depends on the rule: a longer window or fewer holidays (`gap`, `exam days`), more rooms (`seats`), more teachers or fewer invigilators per room (`duties`), or other teachers in `teaching.csv` (`duty room`). Before scheduling, two quick checks catch the obvious cases early: a student with more papers than the window can hold, and a paper bigger than all rooms together.

## 7. Check a plan

`check.py` re-checks a finished plan against every rule in section 5. It's a separate program that shares no code with the planner, so a bug in the planner can't hide from it. Use it after you, or anyone, edits a plan by hand.

```
python check.py <input folder> <plan folder>
python check.py data/tiny output/2026-11-05_15-55-57
```

It never changes a file. When something is wrong, it names the rule, the file, and the row and column:

```
Plan check: 1 problem(s), 1 rule(s) broken.

Rule: column rule (1)
  daywise_seating_plans/2026-11-02/morning/S01.csv, columns 1 and 2: CSE2001 sits in both, side by side.
    column 1: rows 1, 2, 3, 5, 6 (BT2CSE0001, BT2CSE0002, BT2CSE0003, BT2CSE0005, BT2CSE0006)
    column 2: row 4 (BT2CSE0004)
```

It shows the main issue for each mistake, not every follow-on error. A seat with a wrong paper is reported once, not also as "student missing". When it can't tell which of two lines is the real mistake, it shows both and says why, so no problem is hidden.

It checks the yes/no rules only. Preferences, like spreading duties evenly or using rooms in file order, aren't checked, because a plan that misses them still follows the rules.

## 8. Exit codes

Scripts can read the exit code to know how a run went without reading the screen.

| Code | `main.py` (the planner) | `check.py` (the checker) |
|---|---|---|
| 0 | Plan written | Plan is clean |
| 1 | Input data is wrong; every problem is listed | Can't check: the input or plan folder can't be read |
| 2 | No plan possible; reason in `why.txt` | Nothing to check: the folder has only `why.txt` |
| 3 | (not used) | The plan breaks a rule; every problem is listed |

## 9. Datasets included

| Folder | What it is |
|---|---|
| `data/tiny` | 2 cohorts, 16 students, 3 rooms, 9 teachers, 2–6 Nov. Small enough to check by hand. |
| `data/main` | Realistic: 1,600 students in 10 cohorts, 56 papers, 18 S and 18 M rooms, 85 teachers (10 PhD scholars), 2–20 Nov with a holiday on 11 Nov. Made up, not real university data. |
| `data/impossible/` | 7 copies of `tiny`, each broken on purpose so no plan is possible. See its [`README.md`](data/impossible/README.md). |

`tiny` and `main` are written by `python tools/generate_data.py`. Its numbers are at the top of the script, so you can change them and re-run it. The same numbers always give the same files.

## 10. Run the tests

From `prototype1/`:

```
python -m pytest tests
```

There are 124 tests, one file per stage: validate, schedule, seat, duties, no plan and the checker. The checker's tests break one thing in a `tiny` plan each time and confirm it gets caught.

## 11. How it works

One run goes through these stages in order. Each stage is one file.

| Stage | File | What it does |
|---|---|---|
| Load | `loader.py` | Reads the input folder. Only reads, never judges. |
| Validate | `validate.py` | Checks the data (section 4). First that every file is there and readable, then the rules inside. |
| Schedule | `schedule.py` | Gives each paper a date and session. Biggest papers first, each on the earliest day that keeps the gap rule and still has seats and teachers. |
| Seat | `seat.py` | Seats each slot's students in roll order, one paper per room, using every other column. It picks the mix of room sizes that needs the fewest rooms, and splits a paper by section only when a teacher would otherwise have no room. It mixes two papers only if rooms run out. |
| Duties | `duties.py` | Gives every room its teachers. Each teacher's own-paper duty comes first, then everyone else, spread over the days. |
| No plan | `main.py`, `errors.py` | Any stage that finds no plan stops the run; `main.py` writes `why.txt`. |
| Check | `check.py` | Re-reads a finished plan and checks it against the rules, on its own. |

`main.py` runs the stages in order. The planner is greedy and simple on purpose, so every step can be explained: no solver library, and the same input always gives the same plan.

## 12. What it does not do yet

This is prototype 1. It proves the core works before features are added. These are left for later prototypes:

- repeat or backlog students, open and multidisciplinary courses
- buildings, labs, rooms closed on some days
- teacher leave and teacher preferences
- more than two sessions a day, or one paper split over several sittings
- fixing part of a plan by hand and re-planning the rest
- printable reports, door lists, attendance sheets, student timetables
- special-needs seating
- one shift a day per teacher as a strict rule (for now it's only preferred)

## Docs

| File | What it covers |
|---|---|
| [`docs/prototype1_expectations.md`](docs/prototype1_expectations.md) | What the prototype is for and why it's kept small. |
| [`docs/prototype1_model_spec.md`](docs/prototype1_model_spec.md) | Every rule and decision, the build steps, and what is still open. |
| [`docs/data_design_spec.md`](docs/data_design_spec.md) | The rules the input data must follow, and how the example data was designed. |
| [`PROGRESS.md`](PROGRESS.md) | What's done, the decisions made, and why. |

# Prototype 1: model spec

Every rule and decision for prototype1, the build steps, and what is still open.

Each item carries one of three labels:

- **Decided.** Agreed with Ishan. It changes only through the process in §16.
- **Default.** A sensible starting choice. The team may change it if a one-line reason goes in the change log (§16).
- **Open.** The team decides. The decision and its reason are recorded here.

Items not labelled follow the label of their section heading.

---

## 1. Goal (Decided)

Turn an input folder into an exam plan made of three parts: a date sheet, the seating for every room, and the invigilation duties.

- It must be small enough that every teammate can explain it end to end.
- It proves the core engine works before any feature is added.
- Later prototypes add features one at a time.

## 2. Scope

**In (Decided):**

- scheduling papers into slots, two sessions per day, under the gap rule
- seating students in rooms under the column rule
- assigning invigilators
- course codes that are the same paper, listed by hand
- papers shared across cohorts
- input validation
- a short reason when no plan is possible

**In (Default):** program electives, meaning a choice of papers within a cohort. To the tool they are just registrations.

**Out (Decided), for later prototypes:**

- repeat or backlog students
- multidisciplinary or open courses
- buildings (NB/GA/GB), room availability exceptions, labs
- teacher leave and preferences
- pinning an assignment and re-solving
- more than two sessions a day, or one paper over several sittings
- HTML or PDF reports, door lists, attendance sheets, student timetables
- the approval workflow
- the clash graph as an output (it exists only inside the tool)
- special-needs seating

## 3. Vocabulary (Decided, from Phase 0)

| Term | Meaning |
|---|---|
| Program | A degree: BTech CSE, BBA. |
| Cohort | A program plus a year, e.g. `BT2` = BTech 2nd year. |
| Section | Part of a cohort, about 50 students, e.g. `BT2_I`. |
| Course code | The code under which a paper is offered to one cohort. |
| Paper | One question paper, written in one sitting. Several course codes can be one paper. |
| Slot | A date plus a session (`morning` or `evening`). |
| Seat column | One line of seats running from the front of the room to the back. |
| Duty | One teacher in one room for one slot. |

## 4. Command line

```
python main.py <input_dir> [--output <output_root>]
```

- **Decided:** a Python argparse tool with no subcommands. An input folder goes in, and a new timestamped output folder comes out.
- **Default:** run from `prototype1/`.
- **Default:** `--output` defaults to `output/`.
- **Default:** exit code 0 means a plan was written, 1 means the input is invalid, and 2 means no plan is possible.

## 5. Input folder

```
<input_dir>/
├── settings.yaml          parameters: dates, sessions, gap, invigilators per room
├── constraints.yaml       hand-written rules about specific course codes
├── sections.csv           one row per section
├── sections/<section>.csv students of one section
├── courses.csv            one row per course code
├── registrations.csv      which student writes which course code
├── rooms.csv              one row per room
├── teachers.csv           one row per teacher
└── teaching.csv           which teacher teaches which course code to which section
```

- **Decided (Phase 0):** CSV files, one file per section, and registrations and teaching kept as separate tables.
- **Decided (Phase 0):** identifiers only, with no names.
- **Default:** the exact columns and checks are in `data_design_spec.md`.

## 6. `settings.yaml`

```yaml
start_date: 2026-11-02            # first possible exam day
end_date: 2026-11-20              # last possible exam day
exam_weekdays: [Mon, Tue, Wed, Thu, Fri]
holidays: [2026-11-11]            # no exams; still count as gap days
sessions: [morning, evening]      # exactly two
min_gap_days: 2                   # calendar days between a student's exam dates; 2 = one clear day
invigilators_per_room: 2
```

- **Decided:** exactly two sessions.
- **Decided:** the gap is counted in calendar days with `min_gap_days: 2`, and weekends and holidays count.
- **Default:** key names, the date window, and how weekdays and holidays are given.
- General parameters such as "number of days" belong here. Rules about specific papers go in `constraints.yaml`.

## 7. `constraints.yaml`

```yaml
same_paper:              # Decided. Codes that are one question paper.
  - [MTH2001, MTH3011]
```

- **Decided:** `same_paper` lists course codes that are one paper. The codes in a group are scheduled in one slot and treated as one paper for seating and duties. They are entered by hand.
- **Default:** a group's paper ID is its first code. A code not in any group is its own paper.
- **Default:** clashes that come from registrations are never written here, because the tool works them out itself.
- **Open:** separation rules. Ishan's original examples were `[OS, AI, DBMS]` and `[Differential Equations, Calculus 3]`. A bare list can mean several things, so each kind needs its own name and a real use case in the dataset before it is built. Proposed kinds:

  ```yaml
  not_same_slot: [[CSE2003, CSE2004]]   # never in the same slot
  not_same_day:  [[CSE2003, CSE2004]]   # never on the same date
  not_adjacent:  [[MTH2002, MTH3002]]   # different papers that still must not sit side by side
  ```

## 8. Scheduling rules

- **Decided:** each paper gets exactly one slot, and all of its students write it then.
- **Decided:** exams happen only on exam days, which are within the window, an exam weekday, and not a holiday.
- **Decided:** the gap rule. Any two papers of one student are on dates at least `min_gap_days` calendar days apart. So no student has two papers on one day or on consecutive days. Friday then Monday is fine.
- **Decided:** every slot's papers must be seatable (§9) and staffable (§10).
- **Team decision (was Open, changed 2026-11-03):** the scheduler checks while scheduling. A slot may hold at most the seats rooms give with one paper per room (every other seat column: S 12, M 21; 594 in `main`). Then step 5 is asked: a paper goes into a session only if the seating of §9 can really seat that session with it, and the rooms it opens times `invigilators_per_room` must not exceed the number of teachers. Last, the duty rule of §10 is asked: every teacher of every paper in the session must have a room for their paper. Filling every room with teachers is step 6.
- **Team decision (2026-11-03): waiting for another paper.** A paper that would leave a teacher with no room when it is alone (§10) may go into an empty session, which then waits for another paper. Each later paper goes first into a waiting session that it fixes, even if an earlier day is free; otherwise it gets the earliest day as before. A session still waiting at the end means no plan (Rule: duty room). Reason (Krish): waiting is better than skipping, because we have to take the paper.
- **Team decision (was Open):** the algorithm is greedy. Papers go biggest first (ties by paper ID). Each gets the earliest exam day that keeps the gap rule with every clashing paper and has a session it fits in, and goes into the emptier of the two sessions (the first session on a tie).
- **Open:** what makes one valid schedule better than another: a short exam period (the Phase 0 objective), even load across slots, or fewer rooms at the peak. **Default:** finding any valid schedule comes first, and a shorter period is better.
- **Useful fact (Phase 0):** the session doesn't affect the gap rule, because morning and evening of one day are the same date. So papers can be given dates first, and morning or evening chosen afterwards to balance seats and teachers.

## 9. Seating rules

**Rooms (Decided, Phase 0).** A room is a grid of rows by seat columns.

| Type | Benches | Rows | Seat columns | Seats |
|---|---|---|---|---|
| S | 3 benches per row, 1 seat each | 6 | 3 | 18 |
| M | 3 benches per row, 2 seats each | 7 | 6 | 42 |

**Column rule (Decided).** If a seat column holds paper X anywhere, neither neighbouring seat column holds X anywhere.

- The neighbouring column must be either empty or a different paper.
- An empty column counts as separation, so `X _ X` is legal.
- The same paper directly in front or behind is fine.

**Other rules:**

- **Decided:** one paper per room where possible. Papers are mixed only when rooms run out.
  - A room holding one paper uses alternate columns: S holds 12, M holds 21.
  - Two papers alternating fill the room: S holds 18, M holds 42.
- **Team decision (2026-11-03), how to mix when rooms run out:** each paper first fills, alone, the rooms it fills completely. Its last students (too few to fill a room) are its leftover. The leftovers go into the rooms still free, in `rooms.csv` order: the biggest leftover takes the odd columns, and a second leftover joins it in the even columns only if otherwise the leftovers would not fit in the free rooms. The partner is the biggest leftover that fits completely. A room never holds a third paper.
- **Team decision (2026-11-03): a new section starts a new room** when a paper is seated alone and that needs no more rooms for the paper than filling straight on. Reason (Krish): in real life we can't change the data, so the seating needs a way to give each section's teacher a room without their own students (e.g. `tiny`: every student writes CSE2001, so no other paper can share its slot).
- **Decided:** course codes in one `same_paper` group are one paper here.
- **Decided:** every student writing in a slot gets exactly one seat, and a seat holds at most one student.
- **Decided (Phase 0):** each paper's students are seated in roll order, in contiguous chunks.
- **Default:** roll order is `student_id` order. The fill path goes front to back within a column, columns left to right, and rooms in `rooms.csv` order.
- **Default:** rooms open in `rooms.csv` order, a single flat priority as in Phase 0.
- **Default:** a seat column holds at most one paper.
- **Default:** an aisle does not separate columns, so every seat column neighbours the next one.
  - This changes S rooms only: with aisles counted as separation, one paper could fill all 18 seats.

## 10. Duty rules

- **Decided (Phase 0):** `invigilators_per_room` (2) for every open room in every slot, whatever the room size.
- **Decided:** a teacher has at most one duty per slot.
- **Decided (Phase 0):** a teacher never invigilates a room containing a student they teach for the paper being written there. "Teach" comes from `teaching.csv`: a teacher, a course code and a section.
- **Decided (Phase 0):** a teacher invigilates each paper they teach at least once, in a room without their own students. PhD scholars are exempt.
- **Team decision (was Open, widened 2026-11-03):** a teacher who has no room with their paper and none of their own students gets a duty in the same slot as their paper, in a room writing a different paper. This covers a teacher who teaches every section writing the paper, and one whose sections end up in every room of the paper. If no such room is open, there is no plan; step 4 checks this before booking (§8). The "never their own class" rule still holds.
- **Team decision (2026-11-03):** a room holding other sections of a teacher's paper, plus another paper, counts as that teacher invigilating their paper.
- **Default:** spread duties as evenly as possible. PhD scholars may get fewer.
- **Out (later):** rank-weighted fairness, in-domain and out-of-domain pairing, and at most one duty per day.
- The exam cell's current practice (course teachers invigilating their own exam) is not modelled.

## 11. Output folder

```
<output_root>/<timestamp>/
├── schedule.csv
├── duties.csv
└── daywise_seating_plans/
    └── <date>/
        └── <session>/
            └── <room_id>.csv
```

- **Decided:** this layout, with a date sheet, a duty list and one picture CSV per room per slot. Nothing else.
- **Default:** the timestamp is `YYYY-MM-DD_HH-MM-SS` and dates are `YYYY-MM-DD`.
- **Default:** only rooms in use get a file.
- **Default:** `schedule.csv` columns are `date, session, paper_id, course_codes, students`.
- **Default:** `duties.csv` columns are `date, session, room_id, teacher_id`.

**Room CSV (Decided):** a literal picture of the room. One CSV row is one row of seats, starting from the front. One CSV column is one seat column. A blank cell is an empty seat. There is no header row.

- **Default:** a cell reads `<paper_id>:<student_id>`, e.g. `MTH2001:BT2S0042`. The paper is there so anyone can check the column rule by eye.
- **Default:** left and right are as seen by the invigilator at the front.

## 12. When no plan is possible

- **Decided:** the tool says why, in a few lines.
- **Default:** it writes `why.txt` in the timestamped folder, prints the same text, writes no partial plan, and exits with 2.
- **Default:** the reason names the rule and gives the exact numbers. For example:

  ```
  No plan possible.
  Rule: seats
  Slot: 2026-11-04 morning
  Needs 540 seats for MTH2001, CSE3002. Rooms give 504.
  ```

- **Default:** cheap checks run before scheduling, such as more papers for a student than the window allows, or more students than seats.
- **Default:** invalid input is a different failure. List every problem with its file, row and broken rule, then exit with 1. (Idea from `archive/ai_reference_work`.)

## 13. Code rules

- **Decided:** Python and argparse.
- **Default:** Python 3.10 or newer. Libraries are limited to the standard library and PyYAML, plus pytest for tests.
- **Default:** no solver libraries such as OR-Tools or PuLP.
  - **Reason:** the team must be able to explain the engine at lab evals. The archived attempt used a solver, and nobody could.
- **Default:** the same input always gives the same plan. Any randomness uses a fixed seed.
- **Default:** a tiny dataset whose correct plan the team works out by hand before running the tool.
- **Default:** a checker separate from the engine. It re-reads an output folder and checks every Decided rule. (Idea from `archive/ai_reference_work`.)
- **Default:** this layout:

  ```
  prototype1/
  ├── main.py           command line entry point
  ├── ...               one module per stage; names are up to the team
  ├── tools/            dataset generator
  ├── data/<dataset>/   input folders
  ├── tests/
  ├── docs/
  └── output/           generated, ignored by git
  ```

## 14. Build steps

Do one step at a time. Each step is gated: the AI asks questions before it starts and asks for a check after it finishes (`repo_instructions.md` §3).

| # | Step | Check before moving on |
|---|---|---|
| 0 | Understand. The AI explains `prototype1_expectations.md`. No code. | The human describes the tool and the data idea in their own words. |
| 1 | Dataset design. Answer the questions in `data_design_spec.md` §6 with reasons. No code. | The answers and reasons are written in `data_design_spec.md` §8. |
| 2 | Generator. A script in `tools/` writes the `tiny` and `main` input folders. | Open the files and check a few rows by hand against the design. |
| 3 | Load and validate. `main.py` reads an input folder and reports every problem (§12). | Break a file on purpose and read the error. |
| 4 | Schedule. Papers to slots (§8). Writes `schedule.csv`. | Pick a student, list their exam dates, and confirm the gaps by hand. |
| 5 | Seat. Students to seats (§9). Writes the room CSVs. | Open a room CSV and confirm the column rule by eye. |
| 6 | Duties. Teachers to rooms (§10). Writes `duties.csv`. | Pick a teacher and compare their duties with `teaching.csv`. |
| 7 | No plan. The reasons from §12, with one impossible dataset per reason. | Run each one and read the message. |
| 8 | Checker. Checks an output folder against every Decided rule. | Hand-break a room CSV and confirm the checker catches it. |
| 9 | Wrap-up. Run instructions in `prototype1/README.md`. | Each teammate runs `tiny` and explains one stage. |

## 15. Open questions

| # | Question | Default |
|---|---|---|
| 1 | Does an aisle separate seat columns? | No |
| 2 | What does a room CSV cell show? | `paper_id:student_id` |
| 3 | Can one seat column hold two papers? | No |
| 4 | Which separation rules go in `constraints.yaml`, and what do they mean? | None until a use case exists |
| 5 | What makes one valid schedule better than another? | A shorter exam period. **Step 4 (2026-10-28):** the earliest-day greedy gives this; the two sessions of a day are kept balanced |
| 6 | What happens to a teacher who teaches every section of a paper? | **Decided by the team (2026-10-22):** a duty in the same slot, in a room writing a different paper; reported if impossible (§10) |
| 7 | How is duty fairness measured? | Even counts; PhD scholars may get fewer |
| 8 | Are program electives in prototype1? | Yes |
| 9 | What is the paper ID of a `same_paper` group? | Its first code |
| 10 | What are the session names and times? | `morning`, `evening`; times not modelled |

## 16. Changing this spec

- **Decided items:** change them only with proper reasoning. Name the decision, show a concrete problem with it (an example, a failing case, numbers), and say what the change costs. Open a pull request that edits this file and adds a row below. Ishan approves.
- **Default items:** the team may change them. Add a row below with a one-line reason.
- **Open items:** the team decides. Update §15 and add a row below.

### Change log

| Date | Change | Reason | Approved by |
|---|---|---|---|
| 2026-10-13 | First version | — | Ishan |
| 2026-10-22 | §10 and §15 Q6: a teacher who teaches every section of a paper gets a duty in the same slot, in a room writing a different paper | The subject teacher should be present while their paper is written, so they can fix any error in it. They don't need to be in the room with their own students. Needed because the dataset has papers written by one section only (e.g. Thermodynamics, BT2ME). | Pending (Ishan, via PR) |
| 2026-10-28 | §8: how a slot is kept seatable and staffable, and the algorithm (both were Open) | Seats: one paper per room is the spec's normal case and mixing only a fallback; on `main` all 56 papers fit by 20 Nov with no session over 594, so step 5 should not need to mix. Teachers: rooms x 2 <= teachers is cheap and must always hold; the other duty rules need rooms, which exist only after step 5. Biggest first: a big paper uses up so much of a session's 594 seats that only a few sessions can still take it, so it goes first while sessions are empty and smaller papers fill the gaps. Emptier session keeps morning and evening balanced. | Pending (Ishan, via PR) |
| 2026-11-03 | §9: two papers per room in alternating columns, never three; a pair stays together until one paper is finished (was Decided: one paper per room, mixing only when rooms run out) | Problem: with one paper per room in `rooms.csv` order, the last room of each paper is part empty, and on `main` 4 sessions (9 and 12 Nov, both sessions) run out of rooms; 9 Nov evening has 590 students for 594 seats. With two papers per room every session fits, and the whole exam needs 481 rooms instead of 599 (counted the old way), so about 236 fewer duties. Krish: fill the empty columns with a second paper so no room is left half empty, fewer rooms are used and fewer teachers are needed; no student sits next to the same paper; never a third paper in a room; when only one paper is left it goes one paper per room, because that is the only thing we can do. Cost: most rooms hold two question papers, so the invigilator hands out two; sessions with one paper don't change; in step 6 each room has the students of two papers whose teachers must not invigilate it. §8's 594-seat limit is kept as a safe limit. If not approved, step 5 is redone. | Withdrawn by the team the same day (next row) |
| 2026-11-03 | §9 back to one paper per room, mixing only when rooms run out (the row above is withdrawn); how to mix: leftovers share a room only where needed. §8: step 4 asks step 5 whether a session can really be seated | Problem: with two papers per room, the two papers of a slot often share every room, so a teacher who teaches every section of one of them has no room writing a different paper (§10). On `main` this hit 5 teachers (5 Nov evening, 10 Nov morning and evening). Krish: one paper per room is what actually happens in our university; mixing two papers' half-empty last rooms uses the rooms well and keeps the roll order. Second problem: step 4 only counted seats, so 9 Nov evening got 590 students for 594 seats, which one paper per room cannot seat (3 MGT2006 students left over). Now a paper goes into a session only if step 5 can really seat it. Cost: 599 rooms instead of 481, so about 236 more duties; on `main` all 56 papers still fit between 2 and 20 Nov, with 5 mixed rooms. | Pending (Ishan, via PR) |
| 2026-11-03 | §8: step 4 asks the duty rule before booking, and a session may wait for another paper. §9: a new section starts a new room if that costs no extra room. §10: the 2026-10-22 rule widened to any teacher with no room with their paper and none of their own students; a mixed room counts | Problem: HUM2001 (13 Nov) and CSE4004 (10 Nov) were alone in their slots, so T071 and T057, who teach all of them, had no room; in `tiny`, every student writes CSE2001 and both its rooms held both sections, so T003 and T005 had no room. A strict check then refused every empty session for 31 of 56 papers on `main`. Krish: check before booking so the error is stopped early; waiting is better than skipping, because we have to take the paper; in real life we can't change the data, so the seating needs a way to fix this; the widened rule keeps the reason behind the 2026-10-22 rule. Cost: some papers don't get their earliest day; `main` still fits 2–20 Nov (596 rooms, 2 mixed). | Pending (Ishan, via PR) |

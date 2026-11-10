# Prototype 1 progress

Steps are from `docs/prototype1_model_spec.md` §14.

## Done

- **Step 0, understand:** done.
- **Step 1, dataset design:** decisions in `docs/data_design_spec.md` §8 (2026-10-13, redone 2026-10-22).
- **Step 2, generator:** `tools/generate_data.py` writes `data/tiny` and `data/main`. Checked by Krish (Modeling Life: 40 students, 1 teacher, as the 150 rule says). Committed on branch `krish/generator`.

- **Step 3, load and validate:** `main.py`, `loader.py`, `validate.py`, `tests/test_validate.py`. Checked by Krish, committed and pushed on branch `krish/load-validate`.
- **Step 4, schedule:** `schedule.py`, `tests/test_schedule.py`; `main.py` now writes `output/<timestamp>/schedule.csv`. Built on branch `krish/schedule` (from `krish/load-validate`). `main`: 56 papers on 12 days, 2–20 Nov, fullest session 590 of 594 seats. 34 tests pass. Checked by Krish (BT2ECOM0005: Mon 2, Wed 4, Fri 6 Nov, one clear day between each). Committed on branch `krish/schedule`.

- **Step 5, seat:** `seat.py`, `tests/test_seat.py`; `main.py` now also writes `daywise_seating_plans/<date>/<session>/<room>.csv`. Built on branch `krish/seat` (from `krish/schedule`). `main`: 481 room files, 289 with two papers. 51 tests pass. Checked by Krish (9 Nov evening, M03: CSE3003 and CSE4004, no paper in neighbouring columns). Committed on branch `krish/seat`.
- **Step 5 redone (2026-11-03), on `krish/duties`:** one paper per room again, mixing only when rooms run out; step 4 now asks step 5 whether a session can really be seated. New `errors.py` holds `NoPlan`. `main`: 56 papers, 2–20 Nov, 599 rooms, 5 mixed. 54 tests pass. Checked by Krish (9 Nov evening: M16 one paper in columns 1, 3, 5; M17 and M18 mixed, two papers). Committed: spec (`4d2e25e`), code (`0f1afd0`).
- **Step 4 fix (2026-11-03), on `krish/duties`:** new `duties.py` holds the rule for a teacher's own paper; step 4 asks it before booking; a paper that can't be alone waits in an empty session for another paper; in `seat.py` a new section starts a new room when that costs no extra room. `main`: 56 papers, 2–20 Nov, 596 rooms, 2 mixed, every teacher has a room. 63 tests pass. Checked by Krish (13 Nov morning: T071 teaches all of HUM2001, so S01–S04 are out; he takes S05–S07, MEC4003). Committed: spec (`1352df9`), code (`47f5fd8`).

- **Step 6, duties (2026-11-03), on `krish/duties`:** `duties.make_duties()`, 12 new tests in `tests/test_duties.py`; `main.py` now also writes `duties.csv`. `main`: 1,192 duties, each regular teacher 15 or 16, PhD scholars 0, 418 teacher-days with both shifts (about 415 is the least possible). 75 tests pass. Checked by Krish (T071 teaches all of HUM2001, 13 Nov morning, S01–S04: he gets S05, MEC4003, same session, not with his own students). Committed: spec, then code.

- **Step 7, no plan (2026-11-03), on `krish/duties`:** every no-plan stop goes through one path in `main.py`: it prints the reason, writes the same text to `why.txt` (the only file in the new timestamped folder) and exits 2. Every message names its rule. Two cheap checks run before scheduling (`schedule.check_before_scheduling()`): a student with more papers than the window can hold (`Rule: gap`), and a paper bigger than all rooms together (`Rule: seats`). 7 impossible datasets in `data/impossible/` (see its `README.md`); 12 new tests in `tests/test_no_plan.py`. `tiny` and `main` give the same plans as before. 87 tests pass. Checked by Krish (`duty_room_full`: T006 teaches those students, so can't sit in S01; S02, the only other room, has one place and T005 takes it). Committed: code, then notes.

- **Step 8, checker (2026-11-05), on `krish/checker` (from `krish/duties`):** `check.py` re-reads an input folder and a plan folder and checks the 20 yes/no rules of the spec: one slot per paper, exam days, gap, `same_paper`, room shape, column rule, one paper per seat column, at most two papers per room, every student seated once, the paper in its slot, roll order, 2 teachers per room, one duty per slot, never with own students, own-paper duty, duties only in rooms in use, and the plan files. Run: `python check.py data/tiny output/<timestamp>`. Exit 0 clean, 1 can't check (input or plan folder can't be read), 2 nothing to check (only `why.txt`), 3 the plan breaks a rule. It never writes a file. Fresh plans of `tiny` and `main` are clean (`main`: 596 room files, 8,750 seats, 1,192 duties, about a second). 28 new tests in `tests/test_check.py`, each breaking one thing in a `tiny` plan. 115 tests pass. Checked by Krish (2 Nov morning, S01: BT2CSE0004 moved to the middle column; he expected the column rule, and the checker named it, columns 1 and 2, listing both columns' seats). Committed: code (`c89477d`), then notes.

- **Step 9, wrap-up (2026-11-05), on `krish/wrap-up` (from `krish/checker`):** `prototype1/README.md` rewritten as a product guide: what you need, a one-minute try with `tiny`, what the output looks like, how to make your own data (every file with its columns, an example and its checks), the rules every plan follows, what happens on bad input or no plan, the checker, exit codes, datasets, tests, the stages, and what it does not do yet. No code changed. Checked by Krish: he ran README section 2 on his Windows machine (`python main.py data/tiny`, "Wrote output\2026-11-05_16-02-38"; a note on Windows `\` paths was added) and explained the duties stage in his own words (a teacher of a paper is present in that paper's session, but never in a room with the students they taught). Committed: README, then notes. The spec's check is for every teammate: each runs `tiny` from the README and explains one stage.

- **Fix 1, best mix of room sizes (2026-11-09), on `krish/fixes` (from `krish/wrap-up`):** problem: rooms were used in `rooms.csv` order (all S, then all M), so a paper's last few students often got a big room alone; on `main` 31 of 596 rooms were less than half full (2 Nov morning, M12: 3 CSE2001 students in 21 seats). Now `seat.seat_best()` tries the combinations of room sizes for all papers of a slot together and takes the fewest rooms, then the fewest empty seats (Krish: fewest rooms first, because rooms cost teachers). Each paper's chosen rooms are filled in `rooms.csv` order, so roll order and `check.py` are unchanged. A paper is split by section when a teacher of it would otherwise have no room (`schedule.teacher_room_check()`, passed into `seat.seat_slot()` by `schedule.py` and, through `schedule.room_check_for()`, by `main.py`); without that, `tiny` had no plan. Backup: plain `rooms.csv` order, then mixing, as before. `main`: 510 rooms instead of 596, none less than half full, 205 empty one-paper seats instead of 577 (about 118 is the least possible with one paper per room), 0 mixed rooms, 1,020 duties instead of 1,192, each regular teacher 13 or 14, 340 teacher-days with both shifts instead of 418; `tiny` unchanged. `check.py` clean on both. 9 new tests in `tests/test_seat.py`; 4 old tests updated (the hand case now uses 2 rooms not 3, `main` has 510 room files, and 3 tests now seat with the teacher check like `main.py`). 124 tests pass. Spec §9 and change log, README updated.

- **Fix 2, join the leftovers (2026-11-10), on `krish/fixes1` (from `krish/fixes`):** problem: after Fix 1, 48 of 510 rooms on `main` were still part empty, each with 2 invigilators. Krish's aim: one paper per room for as many rooms as possible, and only the leftovers joined. Now `seat.join_leftovers()` runs after the one-paper seating of a slot: a paper's leftover is the students in its last room when that room is part empty; two leftovers share one room (bigger one in the odd columns), best-filling pair first; the shared room is one of the two leftover rooms and must come after both papers' other rooms (roll order); a join is undone if the teacher check fails; never a third paper; full rooms are never touched. `main`: 494 rooms instead of 510 (16 with two papers, 23 to 39 of 42 seats used), 988 duties instead of 1,020, 316 both-shift teacher-days instead of 340. `tiny`: unchanged (7 rooms, 1 with two papers). 134 tests pass (10 new in `tests/test_seat.py`; the old "mixed rooms only when one paper per room does not fit" test is now "a shared room holds only the last students of two papers"; `test_check.py` expects 494 room files). `check.py` is clean on `tiny` and `main` and needed no change. Spec §9 and README updated; change log row 2026-11-10 pending Ishan. Checked by Krish (2 Nov evening, room M12: 13 CSE3001 + 10 ECE4002 students, "okay, no issues") and committed on `krish/fixes1`; Krish pushes.

- **Fix 3, sessions chosen by fewest rooms (2026-11-10), on `krish/fixes2` (from `krish/fixes1`):** problem: the earliest-day rule packed the first days, so busy sessions used all 18 M rooms and then 15 to 18 S rooms (an S room seats 12 of one paper but needs the same 2 invigilators; 194 S rooms on `main`), while 7 of 28 sessions were empty. Now `schedule.make_schedule()` tries three ways in order (`WAYS_IN_ORDER`), each in `schedule.place_papers()`: (a) the session where the paper adds the fewest rooms, tie: fewer students, then earlier day; (b) fewest rooms, tie: earlier day, then fewer students; (c) the old earliest-day way. The first way that places every paper is the plan; `make_schedule()` fills a `report` dict with the way used and the ways that failed. `schedule.session_check()` gives the problem and the room count; results are kept in a dict so the same set of papers is checked once. Krish's reasons: fewer rooms means fewer duties, so teachers can check papers and do other work; fewer students in a session means less crowd at the same time; we can't say no plan, we have to make the plan, and the tool should notify when it falls back. `main`: way (a) fails (ECE2003 has no day left by the gap rule), way (b) makes the schedule: 454 rooms instead of 494 (19 with two papers), 908 duties instead of 988, regular teachers 12 or 13 each, 105 both-shift teacher-days instead of 316, fullest session 570 of 594 (20 Nov morning), still 2 to 20 Nov. `tiny`: unchanged, made by way (a). **Basis lines (Krish, 2026-11-10: the tool should state on what basis the timetable and the seating plan were made; on the screen and in the folder; one line each, because the team explains it to people before):** `schedule.basis_line()` and `seat.basis_line()` give one line each; `main.py` prints them and writes them to `basis.txt` in the plan folder; `check.py` allows `basis.txt` (not checked). 144 tests pass (9 new in `tests/test_schedule.py`, 1 in `tests/test_seat.py`; `test_check.py` expects 454 room files); the test run takes about 1.5 minutes instead of 45 seconds. `check.py` is clean on `tiny` and `main`. Spec §8, §11 and README updated; two change log rows of 2026-11-10 pending Ishan. Checked by Krish (basis lines "really good") and committed on `krish/fixes2`; Krish pushes.

## Next

Branch `krish/duties` (from `krish/seat`, made 2026-11-03). Everything below goes on it, one commit per part, each checked by Krish first:

1. ~~Redo step 5~~ done (see above).
2. ~~Fix step 4~~ done (see above).
3. ~~Step 6: duties~~ done (see above).

4. ~~Step 7: no plan~~ done (see above).

Step 8 (checker) is on its own branch `krish/checker` (from `krish/duties`, made 2026-11-05). Step 9 (wrap-up) is on `krish/wrap-up` (from `krish/checker`, made 2026-11-05). After step 9, prototype1's build steps are all done.

Branch `krish/fixes` (from `krish/wrap-up`, made 2026-11-05) holds fixes found before handing the tool to the real world. Fix 1 (best mix of room sizes) done (see above). Krish decided (2026-11-09) not to reduce empty seats further for now.

Branch `krish/fixes1` (from `krish/fixes`, made 2026-11-10): Fix 2 (join the leftovers) done (see above). Branch `krish/fixes2` (from `krish/fixes1`, made 2026-11-10): Fix 3 (sessions chosen by fewest rooms) built (see above).

## Decisions made in step 2 (2026-10-28)

- IDs: sections `BT2CSE_I`, students `BT2CSE0001`. Reason: easy to read.
- Electives with 150+ students get 2 teachers split by section, others get 1 teacher (model spec §10 rule). Reason: real life (ADS: 3 sections, 2 teachers; a 60-student elective: 1 teacher).
- BT3ECOM has no Big Data or CE&DHA codes. Reason: every BT3ECOM student takes ADS, so nobody would write them.
- `tiny`: 16 students (8 per section). Reason: a broken tool fails on 8 or 16 alike.
- One branch per task: `krish/generator`. Notes live in `prototype1/` because top-level files are off limits.

## Decisions made in step 3 (2026-10-28)

- Two stages (option (a)): stage 1 checks files exist, are readable, headers are right, rows have the right number of values, YAML is valid. If stage 1 fails, stage 2 (the data rules) does not run. Reason (Krish): stops floods of fake follow-on errors from one broken file; a dependency list per check (option (c)) is hard to explain at evals for little gain.
- Errors are grouped by rule with a count above each group, but every problem is still listed with file and row. Reason (Krish): readable screen, and it stays inside model spec §12 and data design spec §3, so no spec change.
- A course code with no registrations, and a teaching row for a section with no student writing that code, are errors (exit 1), as the spec says. Reason (Krish): no students means no exam can be held.
- Two modules: `loader.py` only reads, `validate.py` only checks. Reason (Krish): easier to change later, and each has its own job.
- Row numbers are file line numbers with the header as row 1, as a spreadsheet shows them.

## Decisions made in step 4 (2026-10-28)

- Seat limit per session = one paper per room, every other column (S 12, M 21; 594 in `main`). Reason (Krish): matches the spec's rule that mixing is only a fallback, and on our data step 5 should not need to mix.
- Papers go biggest first (most students), ties by paper ID. Reason (Krish): a big paper uses up so much of a session's 594 seats that only a few sessions can still take it, so it goes first while sessions are empty and smaller papers fill the gaps.
- Each paper gets the earliest exam day that keeps the gap rule and has room. Reason: the spec's Default, a shorter exam period.
- Session choice: option A, the emptier session (morning on a tie). Reason: keeps morning and evening balanced, so neither hits 594 early. Option C (tightest fit) is kept as an idea below.
- Step 4 checks teachers by count only: rooms needed x `invigilators_per_room` <= teachers. Reason (Krish): cheap and must always hold; the other duty rules depend on which room each paper is in, which only exists after step 5, so they belong in step 6.
- If a paper can't be placed, the tool prints a short reason (paper, students, how many days the gap rule or the room limit blocked), writes nothing and exits 2. Step 7 polishes these messages and adds `why.txt`.
- `schedule.csv`: course codes of one paper joined with `;`, `students` is a count.
- Model spec §8 and §15 updated (the two Open items), change log row pending Ishan.

## Decisions made in step 5 (2026-11-03)

- Two papers per room, in alternating columns; never a third paper. This changes a Decided rule in model spec §9 (was: one paper per room, mixing only when rooms run out); change log row pending Ishan. Reason (Krish): no room is left half empty, so fewer rooms and fewer teachers; on `main` the old rule ran out of rooms in 4 sessions (9 and 12 Nov), the new one fits everything in 481 rooms instead of 599. Krish: if Ishan says no, we redo step 5.
- A pair stays together until one paper is finished; that paper's leftover seats in the room stay empty, and the other paper gets a new partner (most students left) in the next room. Reason (Krish's rule). A first version re-picked the pair every room, which spread small papers over up to 17 rooms; fixed, at a cost of 2 rooms (479 to 481).
- When no other paper is left, a paper sits alone in every other column. Reason (Krish): the only thing we can do, as one paper can't use neighbouring columns.
- All sections of a paper are one queue in roll order (`student_id`), so a paper "runs out" only when every section is seated.
- In each room the paper with more students left takes the odd columns (S: 12 vs 6 seats).
- Step 4's 594-seat limit is unchanged; it is now a safe limit (two papers per room give up to 1,080).
- Seating runs before anything is written; if rooms run out, it prints the reason and exits 2.

## Decisions made before step 6 (2026-11-03)

- **Problem found:** the 2026-10-22 team rule (a teacher who teaches every section of a paper gets a duty in the same slot, in a room writing a different paper) could not be met with two papers per room. On `main`, 6 teachers had no such room: in 5 cases the two papers shared every room (5 Nov evening T050; 10 Nov morning T010, T026; 10 Nov evening T025, T032), and in 1 case the paper was alone in its slot (13 Nov morning, HUM2001, T071). On `tiny`, all 6 such teachers failed.
- **A plan never breaks a rule.** If a rule can't be met, the tool says "no plan possible" and exits 2; it never writes a plan with a warning. Reason (Krish): we are making an exam management system, so the plan must follow every rule, not hand over a wrong one.
- **Step 5 goes back to one paper per room**, mixing only when rooms run out (the original Decided rule in model spec §9). The 2026-11-03 two-papers-per-room change is withdrawn. Reason (Krish): this is what actually happens in our university.
- **How to mix when needed:** put two papers' half-empty last rooms together into one room, in alternate columns. Reason (Krish): it uses the rooms well and keeps the roll order.
- **Step 4 fix:** a paper whose teacher teaches all of its students must share its slot with at least one other paper, so the teacher has a room to go to.
- **Step 4 checks the duty rule before booking.** Reason (Krish): it is good to verify early, where the error can come, to prevent it.
- **Waiting for another paper:** a paper that can't be alone may wait in an empty session; later papers fill waiting sessions first; still waiting at the end means no plan. Reason (Krish): waiting is better than skipping, because we have to take the paper.
- **A teacher whose sections are in every room of their paper** (e.g. `tiny` T003) is treated like one who teaches every section: a duty in the same slot, in a room with a different paper. Reason (Krish): it keeps the reason behind the rule.
- **A new section starts a new room** if that costs no extra room. Reason (Krish): in real life we can't change the data, so the tool needs a method to fix this kind of issue.
- **Step 4 asks step 5 first (option A):** a paper goes into a session only if step 5 can really seat it there; otherwise it tries another day or session. Reason (Krish): we are going for one paper per room. The other option (B, two papers in almost every room of a very full slot) was not the university's way.
- **Duties, mixed rooms:** a teacher who teaches only some sections of a paper may meet "invigilate each paper you teach" in a room holding other sections of that paper plus another paper. (Krish: yes, it counts.)
- **PhD scholars get fewer duties:** they are picked only when no other teacher is free. Reason (Krish): invigilation is not their main purpose. UGC has no rule on invigilation counts; its PhD Regulations 2022 allow only 4–6 hours a week of teaching or research assistantship, so research comes first.

## Decisions made in step 6 (2026-11-03)

- **PhD scholars come last:** picked only when no other teacher can be placed. Reason (Krish): "let's not disturb the PhD scholars"; invigilation isn't their main purpose. On `main` they get 0 duties.
- **A plan is found whenever one exists (option b):** before saying no plan, the tool tries a chain of moves: a teacher in a full room moves to another room they may sit in, and so on. Reason (Krish): saying "no solution" is not an option when there is one. Found while building: the chain only matters for own-paper duties, because a teacher with no paper in a slot has no students in any room of it and may sit anywhere.
- **Order for every other place (option i):** no duty yet that day first, then fewest duties so far, then teacher ID. Reason (Krish): a teacher can't do a full day of invigilation, they also check copies and have other work. A strict one shift a day doesn't fit `main` (see "To work on later" below), so for now it is a preference.
- **Two own papers in one slot:** one duty must count for both; if no room does, no plan (Rule: duty room). Not seen on `main` or `tiny`.
- **No plan messages:** "Rule: duty room" when an own-paper duty can't be placed, "Rule: duties" when a room can't get its teachers, with the slot, the short rooms and the counts. `why.txt` is step 7.

## Decisions made in step 7 (2026-11-03)

- **A "no day fits" message lists every reason with its count** (gap days, then sessions blocked by seats, teachers, duty room). Reason (Krish): it gives a better understanding. Rule name: `paper placement`. Counts are now per session, not only the first session of a day.
- **Impossible datasets are real folders** in `data/impossible/`, copies of `tiny` with one thing broken. Reason (Krish): easy to use, and he can tweak them. Cost: if `tiny` changes, they must be re-checked by hand.
- **Backup checks stay** (no dataset, tested directly): `seat.py` running out of rooms, one own paper with no room, two own papers with no shared room, empty `courses.csv`. Reason (Krish): to show we thought of these even if they never happen. Listed with reasons in `data/impossible/README.md`.
- Found: step 4 checks each own paper on its own, so "two own papers in one slot, no one room for both" can still reach step 6. `tiny` has too few sections to show it. Not changed; a possible later fix is for step 4 to check both together.
- Cheap check "more students than seats" is done per paper: one paper alone can use at most the one-paper seats of all rooms (594 in `main`).

## Decisions made in step 8 (2026-11-05)

- **Only the yes/no rules are checked** (20 rules). The "try to" rules (one paper per room where possible, a new section in a new room, rooms in `rooms.csv` order, biggest paper first, PhD scholars last, one shift a day, fewest duties first) are not checked. Reason (Krish): they are preferences, not rules.
- **The checker reads every file with its own code** and imports nothing from the tool (`loader.py`, `schedule.py`, `seat.py`, `duties.py`). Reason (Krish): "we want it error-proof", so a bug in the tool's reading code can't hide from the checker. Cost: about 150 lines that read files a second time.
- **Only the main issue for each mistake.** Reason (Krish): so we can fix it, without unnecessary errors. How: three stages. Stage 1, the plan files are there and the right shape; if not, the checker stops. Stage 2, each schedule row, seat and duty row on its own; a bad seat is reported once and left out of stage 3. Stage 3, the rules over many rows; each room, each paper in a slot and each teacher in a slot is reported at most once. A paper whose date sheet and room files disagree is reported once and left out of the gap and own-paper checks, because its real date is not known.
- **Known case with two lines:** a cell holding an unknown student in place of a real one gives "not a student" and "no seat for <the real one>". The checker can't know which missing student belonged in that seat; guessing could hide a student who really has no seat. Krish: keep both, and print why both lines are shown, because "we don't know which is correct, so I don't want to delete a record I am not sure about; the human gets the whole responsibility for the outcome". The checker prints the reason under the "seated once" line.
- **A column rule problem lists both columns' seats** of that paper (rows and students), so the stray seat is easy to spot. Reason (Krish): it points closer to the error than naming two columns. The checker still can't know which side is wrong.
- **Exit codes:** 0 clean, 1 can't check, 2 only `why.txt`, 3 the plan breaks a rule. Reason (Krish): 1 alone is too general; 3 means an issue in the plan, and the screen names the rule that broke.
- **The checker never writes a file**, not even `why.txt`: the plan folder holds only the three plan parts (model spec §11), and invalid input is a different failure from no plan (§12).
- The spec doesn't change: §13 already asks for a checker separate from the engine.

## Decisions made in step 9 (2026-11-05)

- **The README is a product guide for anyone who wants to make an exam plan**, not only for the team. Reason (Krish): "more like a general product".
- **It teaches how to build your own input data**, every file with its columns, an example and its checks, so a user needs no other document. Reason (Krish): "they will have their own data".
- **No teammate names in the README** (who explains which stage), because it is a product guide.
- One branch for the task: `krish/wrap-up`.

## Generator choices (Default level, open to change)

- A paper = one subject key; a core paper's sections are split into groups of at most 3 (at least 2 groups when 2+ sections). A paper with any elective code follows the elective rule (only Big Data is mixed: core in BT4ECOM, elective in BT3CSE).
- Course codes: department + year + counter, e.g. `CSE3005`.
- Teachers: T001–T015 PROF, T016–T037 ASSOC, T038–T075 ASST, T076–T085 PHD. Groups go to the least-loaded teacher who doesn't already teach that paper.
- Rooms in `rooms.csv`: S01–S18, then M01–M18.

## Open points to discuss

- **To work on later (Krish, 2026-11-03): one shift a day per teacher.** Krish wants each teacher to do only one shift (morning or evening) on a day, because teachers also have copy checking and other work. Not done now (after all steps, maybe). On `main` a strict rule can't fit: 596 rooms over 14 exam days, but one shift a day allows at most 37 rooms a day with 75 regular teachers (518 in all), or 42 with all 85 (588). Today 9 and 12 Nov need 72 rooms each (after Fix 1, 2026-11-09: 510 rooms in all, but 9 and 12 Nov still need 71 each, so it still doesn't fit). A strict rule needs a step 4 check (rooms on a day <= teachers / 2), model spec §10 changed from Out to Decided, and one of: more teachers in the data, a longer window (about 17-18 exam days), or fewer rooms (mixing small leftovers, saves about 25 at most, not enough alone). Step 6 for now only prefers one shift a day (see step 6 decisions).
- **Done 2026-11-09 (Fix 1, best mix of room sizes): too many part-empty rooms.** Kept for history. Not done, and Krish said not to go further for now: putting two papers' part-empty last rooms together even when rooms don't run out (up to 18 fewer rooms on `main`, but bends one paper per room; a team decision), or fewest empty seats first (about 139 empty seats, but about 14 more rooms). Old note: With one paper per room, a paper's last room is rarely full. On `main` (after the step 5 redo), 51 of 599 rooms are part empty: 46 alone rooms (453 empty seats) and the 5 mixed rooms. Worst alone case: 9 Nov morning, M18 holds 3 MGT3002 students in 21 seats. Each such room still needs 2 invigilators. Ideas to discuss later: mix very small leftovers even when rooms don't run out, or let step 4 avoid sessions where a paper would spill a few students into a new room. Not changed now, because one paper per room is the university's way and gives teachers rooms with a different paper (§10).
- **After Fix 2 (2026-11-10), ideas not done:** (a) a leftover could sit in the blank columns of a room another paper already uses, so no leftover needs a room: about 471 rooms on `main`, but 39 rooms with two papers; Krish said no, because one paper per room should stay for as many rooms as possible. (b) A paper could hold back exactly 6 or 21 students on purpose so a shared room is 100% full: not built, to keep the code simple. (c) Only a paper's LAST room counts as a leftover; a part-empty room in the middle of a paper split by section is not joined (it would break roll order). (d) A small paper that fits in one part-empty room is a leftover too (e.g. 18 + 18 students of two papers in one M room); Krish was asked twice whether rooms that are nearly full alone (say 17 or more of 21) should stay alone and gave no answer, so they are still joined. (e) After Fix 3: way (a), Krish's first choice, fails on `main`, so `main` always runs on way (b), and the basis line says so; 20 Nov morning is the tightest session (570 of 594, 6 papers); 6 of 28 sessions are still empty, so a smarter search could save more rooms.
- The 2026-10-13 row "each faculty member teaches 2–3 sections" no longer matches: most teachers now have 1 teaching group, 19 have 2, and a 1-teacher elective covers up to 7 sections.
- Krish's idea for step 6: when teachers run short, the paper's teacher stays nearby instead of in a room. Not in prototype1 as is: buildings and room locations are Out (model spec §2), and "present without a duty" isn't in §10. Discuss at step 6 or keep for a later prototype.
- Krish's caution from step 4: the fullest session in `main` is 590 of 594, only 4 seats spare, so a small enrolment change could break it. `main.py` prints the fullest session after every run. Later idea: if 594 fails, retry with 1,080 (rooms mixed) plus a trial seating. Step 5 now seats two papers per room, so step 4 could use a higher limit; not changed yet.
- Step 6 will need: a mixed room holds students of two papers, so a teacher must not invigilate it if they teach either paper's students there.
- Session choice option C, tightest fit (put a paper where it leaves the fewest empty seats, keeping the other session free for big papers). Not used now because biggest-first already places big papers early. May change later.
- Krish's caution: if teachers can be unavailable in some sessions, the teacher count should use the teachers available in that session, not all of them. Teacher leave is Out of prototype1 (model spec §2), so for now it counts all teachers.

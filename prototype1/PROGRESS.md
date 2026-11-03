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

## Next

Branch `krish/duties` (from `krish/seat`, made 2026-11-03). Everything below goes on it, one commit per part, each checked by Krish first:

1. ~~Redo step 5~~ done (see above).
2. ~~Fix step 4~~ done (see above).
3. ~~Step 6: duties~~ done (see above).

4. ~~Step 7: no plan~~ done (see above).

Next step: step 8, checker (model spec §14).

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

## Generator choices (Default level, open to change)

- A paper = one subject key; a core paper's sections are split into groups of at most 3 (at least 2 groups when 2+ sections). A paper with any elective code follows the elective rule (only Big Data is mixed: core in BT4ECOM, elective in BT3CSE).
- Course codes: department + year + counter, e.g. `CSE3005`.
- Teachers: T001–T015 PROF, T016–T037 ASSOC, T038–T075 ASST, T076–T085 PHD. Groups go to the least-loaded teacher who doesn't already teach that paper.
- Rooms in `rooms.csv`: S01–S18, then M01–M18.

## Open points to discuss

- **To work on later (Krish, 2026-11-03): one shift a day per teacher.** Krish wants each teacher to do only one shift (morning or evening) on a day, because teachers also have copy checking and other work. Not done now (after all steps, maybe). On `main` a strict rule can't fit: 596 rooms over 14 exam days, but one shift a day allows at most 37 rooms a day with 75 regular teachers (518 in all), or 42 with all 85 (588). Today 9 and 12 Nov need 72 rooms each. A strict rule needs a step 4 check (rooms on a day <= teachers / 2), model spec §10 changed from Out to Decided, and one of: more teachers in the data, a longer window (about 17-18 exam days), or fewer rooms (mixing small leftovers, saves about 25 at most, not enough alone). Step 6 for now only prefers one shift a day (see step 6 decisions).
- **To work on (Krish, 2026-11-03): too many part-empty rooms.** With one paper per room, a paper's last room is rarely full. On `main` (after the step 5 redo), 51 of 599 rooms are part empty: 46 alone rooms (453 empty seats) and the 5 mixed rooms. Worst alone case: 9 Nov morning, M18 holds 3 MGT3002 students in 21 seats. Each such room still needs 2 invigilators. Ideas to discuss later: mix very small leftovers even when rooms don't run out, or let step 4 avoid sessions where a paper would spill a few students into a new room. Not changed now, because one paper per room is the university's way and gives teachers rooms with a different paper (§10).
- The 2026-10-13 row "each faculty member teaches 2–3 sections" no longer matches: most teachers now have 1 teaching group, 19 have 2, and a 1-teacher elective covers up to 7 sections.
- Krish's idea for step 6: when teachers run short, the paper's teacher stays nearby instead of in a room. Not in prototype1 as is: buildings and room locations are Out (model spec §2), and "present without a duty" isn't in §10. Discuss at step 6 or keep for a later prototype.
- Krish's caution from step 4: the fullest session in `main` is 590 of 594, only 4 seats spare, so a small enrolment change could break it. `main.py` prints the fullest session after every run. Later idea: if 594 fails, retry with 1,080 (rooms mixed) plus a trial seating. Step 5 now seats two papers per room, so step 4 could use a higher limit; not changed yet.
- Step 6 will need: a mixed room holds students of two papers, so a teacher must not invigilate it if they teach either paper's students there.
- Session choice option C, tightest fit (put a paper where it leaves the fewest empty seats, keeping the other session free for big papers). Not used now because biggest-first already places big papers early. May change later.
- Krish's caution: if teachers can be unavailable in some sessions, the teacher count should use the teachers available in that session, not all of them. Teacher leave is Out of prototype1 (model spec §2), so for now it counts all teachers.

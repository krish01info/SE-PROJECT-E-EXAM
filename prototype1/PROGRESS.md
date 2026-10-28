# Prototype 1 progress

Steps are from `docs/prototype1_model_spec.md` §14.

## Done

- **Step 0, understand:** done.
- **Step 1, dataset design:** decisions in `docs/data_design_spec.md` §8 (2026-10-13, redone 2026-10-22).
- **Step 2, generator:** `tools/generate_data.py` writes `data/tiny` and `data/main`. Checked by Krish (Modeling Life: 40 students, 1 teacher, as the 150 rule says). Committed on branch `krish/generator`.

- **Step 3, load and validate:** `main.py`, `loader.py`, `validate.py`, `tests/test_validate.py`. Checked by Krish, committed and pushed on branch `krish/load-validate`.
- **Step 4, schedule:** `schedule.py`, `tests/test_schedule.py`; `main.py` now writes `output/<timestamp>/schedule.csv`. Built on branch `krish/schedule` (from `krish/load-validate`). `main`: 56 papers on 12 days, 2–20 Nov, fullest session 590 of 594 seats. 34 tests pass. Checked by Krish (BT2ECOM0005: Mon 2, Wed 4, Fri 6 Nov, one clear day between each). Committed on branch `krish/schedule`.

## Next

- Krish pushes `krish/schedule`. Then step 5: seat (model spec §9), writes the room CSVs.

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

## Generator choices (Default level, open to change)

- A paper = one subject key; a core paper's sections are split into groups of at most 3 (at least 2 groups when 2+ sections). A paper with any elective code follows the elective rule (only Big Data is mixed: core in BT4ECOM, elective in BT3CSE).
- Course codes: department + year + counter, e.g. `CSE3005`.
- Teachers: T001–T015 PROF, T016–T037 ASSOC, T038–T075 ASST, T076–T085 PHD. Groups go to the least-loaded teacher who doesn't already teach that paper.
- Rooms in `rooms.csv`: S01–S18, then M01–M18.

## Open points to discuss

- The 2026-10-13 row "each faculty member teaches 2–3 sections" no longer matches: most teachers now have 1 teaching group, 19 have 2, and a 1-teacher elective covers up to 7 sections.
- Krish's idea for step 6: when teachers run short, the paper's teacher stays nearby instead of in a room. Not in prototype1 as is: buildings and room locations are Out (model spec §2), and "present without a duty" isn't in §10. Discuss at step 6 or keep for a later prototype.
- Krish's caution from step 4: the fullest session in `main` is 590 of 594, only 4 seats spare, so a small enrolment change could break it. `main.py` prints the fullest session after every run. Later idea: if 594 fails, retry with 1,080 (rooms mixed) plus a trial seating. Needs step 5 first.
- Session choice option C, tightest fit (put a paper where it leaves the fewest empty seats, keeping the other session free for big papers). Not used now because biggest-first already places big papers early. May change later.
- Krish's caution: if teachers can be unavailable in some sessions, the teacher count should use the teachers available in that session, not all of them. Teacher leave is Out of prototype1 (model spec §2), so for now it counts all teachers.

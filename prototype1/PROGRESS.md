# Prototype 1 progress

Steps are from `docs/prototype1_model_spec.md` §14.

## Done

- **Step 0, understand:** done.
- **Step 1, dataset design:** decisions in `docs/data_design_spec.md` §8 (2026-10-13, redone 2026-10-22).
- **Step 2, generator:** `tools/generate_data.py` writes `data/tiny` and `data/main`. Checked by Krish (Modeling Life: 40 students, 1 teacher, as the 150 rule says). Committed on branch `krish/generator`.

- **Step 3, load and validate:** `main.py`, `loader.py`, `validate.py`, `tests/test_validate.py`. Built on branch `krish/load-validate` (from `krish/generator`). Waiting for Krish's check (break a file, read the error).

## Next

- Step 3 check, then commit. Then step 4: schedule (model spec §8), writes `schedule.csv`.

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

## Generator choices (Default level, open to change)

- A paper = one subject key; a core paper's sections are split into groups of at most 3 (at least 2 groups when 2+ sections). A paper with any elective code follows the elective rule (only Big Data is mixed: core in BT4ECOM, elective in BT3CSE).
- Course codes: department + year + counter, e.g. `CSE3005`.
- Teachers: T001–T015 PROF, T016–T037 ASSOC, T038–T075 ASST, T076–T085 PHD. Groups go to the least-loaded teacher who doesn't already teach that paper.
- Rooms in `rooms.csv`: S01–S18, then M01–M18.

## Open points to discuss

- The 2026-10-13 row "each faculty member teaches 2–3 sections" no longer matches: most teachers now have 1 teaching group, 19 have 2, and a 1-teacher elective covers up to 7 sections.
- Krish's idea for step 6: when teachers run short, the paper's teacher stays nearby instead of in a room. Not in prototype1 as is: buildings and room locations are Out (model spec §2), and "present without a duty" isn't in §10. Discuss at step 6 or keep for a later prototype.

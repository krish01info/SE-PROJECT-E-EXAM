# Prototype 1 progress

Steps are from `docs/prototype1_model_spec.md` §14.

## Done

- **Step 0, understand:** done.
- **Step 1, dataset design:** decisions in `docs/data_design_spec.md` §8 (2026-10-13, redone 2026-10-22).
- **Step 2, generator:** `tools/generate_data.py` writes `data/tiny` and `data/main`. Checked by Krish (Modeling Life: 40 students, 1 teacher, as the 150 rule says). Committed on branch `krish/generator`.

## Next

- Step 3: load and validate. `main.py` reads an input folder and lists every problem with file, row and rule, then exits 1.

## Decisions made in step 2 (2026-10-28)

- IDs: sections `BT2CSE_I`, students `BT2CSE0001`. Reason: easy to read.
- Electives with 150+ students get 2 teachers split by section, others get 1 teacher (model spec §10 rule). Reason: real life (ADS: 3 sections, 2 teachers; a 60-student elective: 1 teacher).
- BT3ECOM has no Big Data or CE&DHA codes. Reason: every BT3ECOM student takes ADS, so nobody would write them.
- `tiny`: 16 students (8 per section). Reason: a broken tool fails on 8 or 16 alike.
- One branch per task: `krish/generator`. Notes live in `prototype1/` because top-level files are off limits.

## Generator choices (Default level, open to change)

- A paper = one subject key; a core paper's sections are split into groups of at most 3 (at least 2 groups when 2+ sections). A paper with any elective code follows the elective rule (only Big Data is mixed: core in BT4ECOM, elective in BT3CSE).
- Course codes: department + year + counter, e.g. `CSE3005`.
- Teachers: T001–T015 PROF, T016–T037 ASSOC, T038–T075 ASST, T076–T085 PHD. Groups go to the least-loaded teacher who doesn't already teach that paper.
- Rooms in `rooms.csv`: S01–S18, then M01–M18.

## Open points to discuss

- The 2026-10-13 row "each faculty member teaches 2–3 sections" no longer matches: most teachers now have 1 teaching group, 19 have 2, and a 1-teacher elective covers up to 7 sections.
- Krish's idea for step 6: when teachers run short, the paper's teacher stays nearby instead of in a room. Not in prototype1 as is: buildings and room locations are Out (model spec §2), and "present without a duty" isn't in §10. Discuss at step 6 or keep for a later prototype.

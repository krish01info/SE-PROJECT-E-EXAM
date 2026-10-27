# Start here

**Current state:** step 2 (generator) is done and committed on branch `krish/generator`, in two commits: the spec rows, then the generator. `python tools/generate_data.py` (run from `prototype1/`) writes `data/tiny` and `data/main`, and all checks pass.

**Open problems:** see "Open points to discuss" in `PROGRESS.md`.

**Exact next step:** Krish pushes `krish/generator` and opens a PR into `main`. Then step 3, load and validate (model spec §14): `main.py` reads an input folder and lists every problem with file, row and rule, then exits 1. Start it with the step gate from `repo_instructions.md` §3: say the plan, ask 1–3 questions, wait for answers.

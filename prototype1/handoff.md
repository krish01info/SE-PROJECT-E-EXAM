# Start here

**Current state:** step 3 (load and validate) is written on branch `krish/load-validate`, made from `krish/generator`. Not committed yet: it waits for Krish's step check. `python main.py data/tiny` and `python main.py data/main` both print "Input OK" and exit 0; `python -m pytest tests` passes (18 tests).

**Open problems:** see "Open points to discuss" in `PROGRESS.md`. `krish/generator` still needs its PR into `main`.

**Exact next step:** Krish breaks a file on purpose, runs `python main.py <folder>`, and reads the error (model spec §14 step 3 check). Then commit step 3. Then step 4, schedule (model spec §8), starting with the step gate from `repo_instructions.md` §3.

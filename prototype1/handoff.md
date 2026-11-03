# Start here

**Current state:** on branch `krish/duties` (from `krish/seat`). Done here, each checked by Krish and committed: step 5 redo (one paper per room, mix only when rooms run out), step 4 fix (step 4 asks step 5 and the duty rule before booking) and step 6, duties (`duties.make_duties()`, writes `duties.csv`). `main`: 56 papers, 2–20 Nov, 596 rooms, 1,192 duties, each regular teacher 15 or 16, PhD scholars 0. 75 tests pass. Nothing on this branch is pushed by Claude; Krish pushes.

**Open problems:** tell Ishan the two-papers-per-room change is withdrawn; change log rows of 2026-10-22, 2026-10-28 and the 2026-11-03 rows (step 5 redo, step 4 fix, step 6 duties) are pending him. To work on later (`PROGRESS.md`, "Open points"): part-empty rooms, and Krish's wish for one shift a day per teacher (doesn't fit `main` yet: 596 rooms, at most 518 with one shift a day). `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`.

**Git in this folder from a Linux shell:** use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Tests from a Linux shell without pytest:** pytest can't be installed there (no network). Claude used a small stand-in runner kept outside the repo; on Krish's machine, `python -m pytest tests` works as usual.

**Exact next step:** step 7, no plan (model spec §12 and §14): every no-plan reason gets a clear message and `why.txt` in the timestamped folder, plus one impossible dataset per reason. Step gate first (`repo_instructions.md` §3).

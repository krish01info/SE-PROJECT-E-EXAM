# Start here

**Current state:** on branch `krish/duties` (from `krish/seat`). Done here, each checked by Krish and committed: step 5 redo, step 4 fix, step 6 duties, step 7 no plan (`why.txt`, a rule on every message, two cheap checks before scheduling, 7 impossible datasets in `data/impossible/` with a README). `main`: 56 papers, 2–20 Nov, 596 rooms, 1,192 duties. 87 tests pass. Nothing on this branch is pushed by Claude; Krish pushes.

**Open problems:** tell Ishan the two-papers-per-room change is withdrawn; change log rows of 2026-10-22, 2026-10-28 and the 2026-11-03 rows (step 5 redo, step 4 fix, step 6 duties) are pending him. To work on later (`PROGRESS.md`, "Open points"): part-empty rooms, and Krish's wish for one shift a day per teacher (doesn't fit `main` yet: 596 rooms, at most 518 with one shift a day). `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`.

**Git in this folder from a Linux shell:** use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Tests from a Linux shell without pytest:** pytest can't be installed there (no network). Claude used a small stand-in runner kept outside the repo; on Krish's machine, `python -m pytest tests` works as usual.

**Exact next step:** step 8, checker (model spec §14): re-reads an output folder and checks every Decided rule; check = hand-break a room CSV and see the checker catch it. Step gate first (`repo_instructions.md` §3). Also open from step 7: step 4 checks each own paper alone, so "two own papers, no one room for both" can still reach step 6 (`PROGRESS.md`, step 7 decisions).

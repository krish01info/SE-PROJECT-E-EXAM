# Start here

**Current state:** on branch `krish/wrap-up` (from `krish/checker`, made 2026-11-05). Step 9, wrap-up: `prototype1/README.md` rewritten as a product guide (run, output, own data, rules, errors, checker, exit codes, tests, stages, limits). Checked by Krish (ran section 2 on Windows, explained duties) and committed: README, then notes. Step 8 (checker) is committed and pushed on `krish/checker` (`adbd938`). 115 tests pass. Nothing is pushed by Claude; Krish pushes.

**Open problems:** Tell Ishan the two-papers-per-room change is withdrawn; change log rows of 2026-10-22, 2026-10-28 and 2026-11-03 are pending him. To work on later (`PROGRESS.md`, "Open points"): part-empty rooms, one shift a day per teacher. `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat`, `krish/duties`, `krish/checker`, `krish/wrap-up` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`. Step 7 open point: "two own papers, no one room for both" can still reach step 6 (it stops there with no plan, so never a bad plan).

**Git in this folder from a Linux shell:** use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Tests from a Linux shell:** pytest was installed there with `pip install --user --break-system-packages pytest` (2026-11-05, outside the repo). On Krish's machine, `python -m pytest tests` works as usual.

**Exact next step:** Krish pushes `krish/wrap-up`. The spec's full check is for every teammate: each runs `tiny` from the README and explains one stage. After that, prototype1's build steps are all done: open PRs into `main` (Krish writes the why).

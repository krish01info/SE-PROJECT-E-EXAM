# Start here

**Current state:** on branch `krish/checker` (from `krish/duties`, made 2026-11-05). Step 8, checker, is done, checked by Krish and committed: code `c89477d`, then notes. `python check.py data/tiny output/<timestamp>` checks a plan against the 20 yes/no rules; exit 0 clean, 1 can't check, 2 only `why.txt`, 3 a rule broken. Fresh `tiny` and `main` plans are clean. 115 tests pass. Nothing is pushed by Claude; Krish pushes (`krish/duties` and `krish/checker`).

**Open problems:** Tell Ishan the two-papers-per-room change is withdrawn; change log rows of 2026-10-22, 2026-10-28 and 2026-11-03 are pending him. To work on later (`PROGRESS.md`, "Open points"): part-empty rooms, one shift a day per teacher. `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat`, `krish/duties`, `krish/checker` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`. Step 7 open point: "two own papers, no one room for both" can still reach step 6 (it stops there with no plan, so never a bad plan).

**Git in this folder from a Linux shell:** use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Tests from a Linux shell:** pytest was installed there with `pip install --user --break-system-packages pytest` (2026-11-05, outside the repo). On Krish's machine, `python -m pytest tests` works as usual.

**Exact next step:** step 9, wrap-up (model spec §14): run instructions in `prototype1/README.md`; check = each teammate runs `tiny` and explains one stage. Step gate first (`repo_instructions.md` §3).

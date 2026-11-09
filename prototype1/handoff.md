# Start here

**Current state:** on branch `krish/fixes` (from `krish/wrap-up`, made 2026-11-05), for fixes before handing the tool to the real world. Fix 1, best mix of room sizes (2026-11-09), is done: `seat.py` tries the combinations of S and M rooms for each slot and takes the fewest rooms, then the fewest empty seats; a paper is split by section only when a teacher of it would otherwise have no room. `main`: 510 rooms instead of 596, none less than half full, 1,020 duties instead of 1,192. 124 tests pass; `check.py` is clean on `tiny` and `main`. Details in `PROGRESS.md` (Fix 1) and spec §9 (2026-11-09 row). Nothing is pushed by Claude; Krish pushes.

**Open problems:** Krish decided not to cut empty seats further for now (ideas in `PROGRESS.md`, "Open points"). The 2026-11-09 change log row and the earlier rows of 2026-10-22, 2026-10-28 and 2026-11-03 are pending Ishan. Tell Ishan the two-papers-per-room change is withdrawn. One shift a day per teacher still doesn't fit `main` (9 and 12 Nov need 71 rooms each). `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat`, `krish/duties`, `krish/checker`, `krish/wrap-up`, `krish/fixes` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`. Step 7 open point: "two own papers, no one room for both" can still reach step 6 (it stops there with no plan, so never a bad plan).

**Git in this folder from a Linux shell:** use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Tests from a Linux shell:** pytest was installed there with `pip install --user --break-system-packages pytest` (2026-11-05, outside the repo). On Krish's machine, `python -m pytest tests` works as usual.

**Exact next step:** Krish checks Fix 1 (run `python main.py data/main`, open one room file, e.g. 2 Nov morning, and `python -m pytest tests`), then pushes `krish/fixes`. Then the next fix, or PRs into `main` (Krish writes the why).

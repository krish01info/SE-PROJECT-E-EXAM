# Start here

**Current state:** on branch `krish/duties` (from `krish/seat`). Step 5 redone and committed here: one paper per room, mixing only when rooms run out, and step 4 asks step 5 whether a session can really be seated (`4d2e25e` spec, `0f1afd0` code). `main`: 56 papers, 2–20 Nov, 599 rooms, 5 mixed. 54 tests pass. Not pushed.

**Open problems:** tell Ishan the 2026-11-03 two-papers-per-room change is withdrawn; the 2026-10-22, 2026-10-28 and new 2026-11-03 change log rows are pending him. 51 of 599 rooms are part empty (see "To work on" in `PROGRESS.md`). `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`.

**Git in this folder from a Linux shell:** files on disk have Windows line endings, so use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Exact next step:** step 4 fix: a paper whose teacher teaches all of its students (HUM2001, T071, 13 Nov morning) must never be alone in its slot. Step gate first (`repo_instructions.md` §3). Then step 6 duties.

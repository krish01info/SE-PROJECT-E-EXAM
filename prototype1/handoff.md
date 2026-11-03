# Start here

**Current state:** on branch `krish/duties` (from `krish/seat`). Done here: step 5 redone (one paper per room, mix only when rooms run out) and the step 4 fix (step 4 asks step 5 and the duty rule before booking; a paper that can't be alone waits for another paper; a new section starts a new room if it costs no extra room). `duties.py` holds the rule for a teacher's own paper. `main`: 56 papers, 2–20 Nov, 596 rooms, 2 mixed, every teacher has a room for each paper they teach. 63 tests pass. Commits up to `47f5fd8` are not pushed yet (Krish pushes).

**Open problems:** tell Ishan the two-papers-per-room change is withdrawn; change log rows of 2026-10-22, 2026-10-28 and the two of 2026-11-03 are pending him. Part-empty rooms to work on later (`PROGRESS.md`, "To work on"). `krish/generator`, `krish/load-validate`, `krish/schedule`, `krish/seat` still need PRs into `main`. `data/demo/` is an untracked copy of `tiny`.

**Git in this folder from a Linux shell:** files on disk have Windows line endings, so use `git -c core.autocrlf=true ...`, or every file shows as changed. Committing needs delete permission (git removes its lock files). Author: Krish Sharma <krish425988888@gmail.com>.

**Exact next step:** step 6, duties (model spec §10): fill every room with 2 teachers, write `duties.csv` (`date, session, room_id, teacher_id`). Decided already: each teacher (not PhD) gets one duty for each paper they teach, in a room from `duties.paper_duty_rooms()`; never a room with their own students; at most one duty per slot; PhD scholars get fewer duties (picked only when no other teacher is free); spread duties evenly. If a room can't get 2 teachers: no plan, exit 2. Step gate first (`repo_instructions.md` §3).

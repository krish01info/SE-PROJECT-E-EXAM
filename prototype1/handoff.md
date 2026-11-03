# Start here

**Current state:** step 5 (seat) is done, checked by Krish and committed on branch `krish/seat` (made from `krish/schedule`): one commit for the code, one for the model spec §9 change, one for these notes. `python main.py data/tiny` and `python main.py data/main` write `output/<timestamp>/schedule.csv` and `daywise_seating_plans/<date>/<session>/<room>.csv`, and exit 0. `main`: 481 room files, 289 with two papers. 51 tests pass.

**How seating works:** two papers per room in alternating columns, never three; a pair stays together until one paper is finished, then the other gets a new partner; a paper with no partner left sits alone in every other column. See `seat.py` docstring.

**Open problems:** the §9 change (two papers per room) changes a Decided rule and needs Ishan's approval; Krish is asking him. If he says no, redo step 5. `krish/generator`, `krish/load-validate`, `krish/schedule` and `krish/seat` still need PRs into `main`. `data/demo/` is an untracked local copy of `tiny`, not committed. Other points: "Open points to discuss" in `PROGRESS.md`.

**Exact next step:** Krish pushes `krish/seat`. Then step 6, duties (model spec §10): teachers to rooms, writes `duties.csv`. Start a new branch `krish/duties` from `krish/seat`, then the step gate from `repo_instructions.md` §3. Note for step 6: a room can hold students of two papers.

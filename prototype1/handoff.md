# Start here

**Current state:** step 4 (schedule) is done, checked by Krish and committed on branch `krish/schedule` (made from `krish/load-validate`): one commit for the code, one for the model spec change. `python main.py data/tiny` and `python main.py data/main` write `output/<timestamp>/schedule.csv` and exit 0. `main`: 56 papers on 12 days, fullest session 590 of 594 seats. `python -m pytest tests` passes (34 tests).

**Open problems:** see "Open points to discuss" in `PROGRESS.md` (only 4 seats spare in the fullest session; option C for sessions; teacher availability). `krish/generator`, `krish/load-validate` and `krish/schedule` still need PRs into `main`; the spec change rows need Ishan's approval.

**Exact next step:** step 5, seat (model spec §9): students to seats in each session's rooms, writes `daywise_seating_plans/<date>/<session>/<room>.csv`. Start a new branch `krish/seat` from `krish/schedule` (after Krish has pushed it), then the step gate from `repo_instructions.md` §3.

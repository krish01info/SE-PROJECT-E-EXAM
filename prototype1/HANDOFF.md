# Prototype 1 Session Handoff

Saved: 2026-10-21; updated: 2026-10-22. This is a continuation summary, not a
verbatim chat transcript.

## Where we stopped

The user asked whether the current system meets the MVP, received the checklist
below, and then asked to save the conversation so work can resume here. On
2026-10-22, they requested committing the changes and including this checklist
in the commit message. No next implementation task has been selected. The
suggested next piece is the standalone output checker, followed by reusable
impossible datasets.

## Working context

- Branch: `Himank/paper-scheduler`.
- Read `repo_instructions.md`, this prototype's README, and its specs before work.
- The user explicitly requested implementation on their branch and said the team
  will review once a prototype is built, rather than stopping for individual step
  reviews during this work. Preserve that conversation context.
- The user authorized local commits on 2026-10-22, with the MVP checklist in the
  implementation commit message. Keep the spec change in its own commit per the
  repository instructions. No push, merge, or pull request was requested. Spec
  decisions remain pending Ishan review.
- Before this feature, `main.py`, the model spec, `scheduler.py`, and scheduler
  tests already had local changes. Preserve the combined working tree.

## Decisions from this conversation

1. A seating layout that cannot be staffed is only an internal candidate during
   the current search. Try other legal layouts in that slot before moving papers
   to another slot. Do not export incomplete plans or persist candidates between
   runs. More teachers added later require another run.
2. A teacher who teaches every section writing a paper is exempt from the
   requirement to supervise that paper. The user cited a real situation their
   team encountered. The exemption applies to that teacher-paper pair only and
   is printed with its reason. Supervising their own students remains forbidden.
3. Preserve the existing column rule, roll order, room priority, and mixing rule:
   mixed rooms are permitted only when separate-paper seating cannot fit everyone.

These decisions and their reasons are recorded in
`docs/prototype1_model_spec.md` §§8, 10, 15, and the change log.

## Current implementation

- `scheduler.py`: deterministic date/session backtracking. Uses safe capacity
  bounds during placement and exact resource checks before accepting a schedule.
  Returns an `ExamPlan` with the schedule and room/duty plans.
- `resources.py`: searches legal room allocations and column patterns, seats
  sorted student chunks, and matches eligible teachers to duties. Required
  own-paper teachers are matched first; other places prefer lower duty counts.
- `main.py`: loads resource data and exports `schedule.csv`, `duties.csv`, and
  `daywise_seating_plans/<date>/<session>/<room>.csv` only after finding a complete
  plan. Invalid input exits 1; infeasible input writes only `why.txt` and exits 2.
- `README.md`: updated status and run/test instructions.
- `tests/`: scheduler, resource, and exported-output checks. Last run: **21 tests
  passed**. Both bundled datasets produce deterministic complete plans.

Important search detail: an unstaffable partial slot may become feasible when
another paper makes mixing permissible and reduces the number of rooms. Do not
prune it using an exact staffing failure prematurely. A regression test covers
this case. Exact teacher matching must also enforce one duty per teacher per
slot and every applicable own-paper requirement, not merely teacher totals.

## User's verified output

The user ran `python3 main.py data/main` from `prototype1/`.
Output: `output/2026-10-21_19-15-13/` (generated and ignored by Git).
Its actual files passed the independent checks implemented in the test suite.

- 288 students; 24 course codes grouped into 16 papers.
- Exam dates: Nov 2, 4, 6, 9, and 13, 2026.
- First four dates: AIML and ECE core papers together in the morning (192
  students), Cyber core paper in the evening (96 students).
- Nov 13: three shared electives in the morning (216 students), the fourth in
  the evening (72). Students take one elective each, so these do not clash.
- 50 room seating files across 10 sessions; 100 individual teacher duties.
  These are repeated room uses, not 50 different rooms.
- Teachers have 5–7 duties each. No all-sections exemption was needed here.
- Example: T001 supervises AIM2201 in Nov 2 morning M05, containing section II
  students, while teaching section I.

## MVP checklist at handoff

- [x] Input loading/validation and generators for `tiny` and `main`.
- [x] Scheduling, shared-paper grouping, allowed dates, and student exam gaps.
- [x] Legal seating, room mixing rules, roll order, and complete student coverage.
- [x] Eligible invigilators, no double-booking, own-paper rules and exemptions.
- [x] Retry seating and backtrack scheduling when resources fail.
- [x] Complete CSV exports, tested failures without partial plans, determinism.
- [x] All 21 current tests pass, including end-to-end output checks.
- [ ] Standalone checker for an arbitrary output folder; current checks live in
  tests rather than a user-facing checker command.
- [ ] Reusable `impossible_days`, `impossible_seats`, and `impossible_teachers`
  dataset folders. Related failures have tests, but these folders do not exist.
- [ ] Deliberately corrupt output files and demonstrate checker rejection.
- [ ] Document/confirm a hand-solved expected result for `tiny`.
- [ ] Team runs `tiny`, explains the stages, and reviews the pending decisions.
- [ ] Improve generic staffing failures to identify the blocked teacher/room.

The core workflow works; full MVP acceptance is unfinished. Duty fairness is
best effort rather than globally optimized. Exhaustive backtracking may be slow
for larger or difficult impossible datasets. A website and reports are outside
this prototype's scope.

## Resume commands

From the repository root:

```sh
git status --short --branch
cd prototype1
python3 -B -m unittest discover -s tests -v
python3 main.py data/tiny
python3 main.py data/main
```

Python 3.10+ and PyYAML are required. No new third-party dependency was added.

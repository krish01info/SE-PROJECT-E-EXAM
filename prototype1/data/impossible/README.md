# Impossible datasets (step 7)

Each folder is a copy of `data/tiny` with one thing broken on purpose, so that no plan is possible. Run one from `prototype1/`:

```
python main.py data/impossible/<folder>
```

The tool prints why, writes the same text to `why.txt` in a new folder under `output/`, writes nothing else, and exits with 2 (model spec §12).

They are real folders, not built by the tests, so they are easy to use and easy to tweak (Krish, 2026-11-03). If `tiny` changes, these copies do not change with it: re-check them by hand.

| Folder | What is broken (compared with `tiny`) | Rule in the message |
|---|---|---|
| `no_exam_days` | `settings.yaml`: `exam_weekdays: [Sat]`, but 2–6 Nov 2026 is Mon–Fri | `exam days` |
| `window_too_short` | `settings.yaml`: `end_date: 2026-11-04`. 3 days with a 2-day gap fit only 2 papers, and every student has 3 | `gap` |
| `paper_too_big` | `rooms.csv`: only S01 (12 seats for one paper), but CSE2001 has 16 students | `seats` |
| `no_day_fits` | `settings.yaml`: `invigilators_per_room: 5`. CSE2001 needs 2 rooms, so 10 teachers, and there are 9 | `paper placement` |
| `waiting_paper` | `teaching.csv`: T005 also teaches CSE2003 to BT2ECOM_I, so T005 teaches every student of CSE2001. Every student writes CSE2001, so no other paper can share its slot and give T005 a room | `duty room` |
| `duty_room_full` | `settings.yaml`: `invigilators_per_room: 1`; `teaching.csv`: T006 also teaches CSE2001 to BT2CSE_I. T005 and T006 both need S02, which has one place | `duty room` |
| `too_few_teachers` | `settings.yaml`: `invigilators_per_room: 3`; `teaching.csv`: T009 (PhD) teaches all four electives. 6 Nov morning needs all 9 teachers, but T009 has own students in every room | `duties` |

## Reasons with no dataset (backup checks)

These checks stay in the code to show we thought of them, even though `main.py` never reaches them on a valid input (Krish, 2026-11-03). Each is tested by calling its function directly.

| Check | Why it isn't reached | Test |
|---|---|---|
| `seat.py`: rooms run out in a slot (`Rule: seats`) | Step 4 asks `seat.seat_slot()` before it books a session | `tests/test_seat.py::test_a_room_never_holds_a_third_paper` |
| `duties.py`: a teacher's one own paper has no room (`Rule: duty room`) | Step 4 checks every paper's teachers before it books a session | `tests/test_no_plan.py::test_backup_one_own_paper_with_no_room` |
| `duties.py`: two own papers in one slot and no one room counts for both (`Rule: duty room`) | Can happen, because step 4 checks each paper on its own. But both papers need a section the teacher doesn't teach, in different rooms, and `tiny` has too few sections for that | `tests/test_duties.py::test_no_plan_when_two_own_papers_need_different_rooms` |
| `main.py`: no papers (`Rule: papers`) | Validation already stops an empty `courses.csv` (every student needs a registration) | none: validation tests cover it |

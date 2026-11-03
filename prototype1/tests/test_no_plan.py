"""Step 7 tests: when no plan is possible (model spec section 12).

Every folder in data/impossible/ must stop with exit 2, name its rule, and
write only why.txt holding the same text it prints.

Run from prototype1/:

    python -m pytest tests
"""

import datetime
import sys
from pathlib import Path

import pytest

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import duties  # noqa: E402
import main  # noqa: E402
import schedule  # noqa: E402
import seat  # noqa: E402
from errors import NoPlan  # noqa: E402

IMPOSSIBLE = PROTOTYPE / "data" / "impossible"

# Folder in data/impossible/ -> the rule its message must name.
EXPECTED_RULE = {
    "no_exam_days": "exam days",
    "window_too_short": "gap",
    "paper_too_big": "seats",
    "no_day_fits": "paper placement",
    "waiting_paper": "duty room",
    "duty_room_full": "duty room",
    "too_few_teachers": "duties",
}


def test_every_impossible_folder_has_a_test():
    # A new folder in data/impossible/ must be added to EXPECTED_RULE.
    folders = {path.name for path in IMPOSSIBLE.iterdir() if path.is_dir()}
    assert folders == set(EXPECTED_RULE)


@pytest.mark.parametrize("dataset", sorted(EXPECTED_RULE))
def test_impossible_dataset_says_why(dataset, tmp_path, capsys):
    out_root = tmp_path / "out"
    code = main.main([str(IMPOSSIBLE / dataset), "--output", str(out_root)])
    out = capsys.readouterr().out
    assert code == 2, out

    # One new folder, and only why.txt in it: no half plan.
    folders = list(out_root.iterdir())
    assert len(folders) == 1
    assert [path.name for path in folders[0].iterdir()] == ["why.txt"]

    why = (folders[0] / "why.txt").read_text(encoding="utf-8")
    lines = why.splitlines()
    assert lines[0] == "No plan possible."
    assert lines[1] == f"Rule: {EXPECTED_RULE[dataset]}"
    assert len(lines) >= 3                 # the numbers come after the rule
    assert why in out                      # printed text = why.txt


def test_valid_input_writes_no_why_txt(tmp_path, capsys):
    assert main.main([str(PROTOTYPE / "data" / "tiny"),
                      "--output", str(tmp_path)]) == 0
    assert not list(tmp_path.glob("*/why.txt"))


# ------------------------------------------------- cheap checks

def days(*numbers):
    return [datetime.date(2026, 11, number) for number in numbers]


def test_most_papers_in_window():
    # Mon 2 to Fri 6 Nov, gap 2: 2, 4, 6.
    assert schedule.most_papers_in_window(days(2, 3, 4, 5, 6), 2) == 3
    # Mon 2 to Wed 4 Nov: 2 and 4 only.
    assert schedule.most_papers_in_window(days(2, 3, 4), 2) == 2
    # Fri 6 and Mon 9 are 3 days apart, so a gap of 3 still fits both.
    assert schedule.most_papers_in_window(days(6, 9), 3) == 2
    assert schedule.most_papers_in_window([], 2) == 0


def test_cheap_checks_pass_when_everything_fits():
    papers = {"A": schedule.Paper("A", ["A"], {"s1", "s2"}),
              "B": schedule.Paper("B", ["B"], {"s1"})}
    schedule.check_before_scheduling(papers, days(2, 4), 2, seat_limit=2,
                                     room_count=1)       # no error


# ------------------------------------------------- backup checks

def test_backup_one_own_paper_with_no_room():
    # Backup: step 4 stops this before booking, so main.py never gets
    # here. T1 teaches P to A_I, and the only room holds A_I's students.
    plans = [seat.RoomPlan("R1", ["P"], [[("P", "a1")]])]
    with pytest.raises(NoPlan) as error:
        duties.own_paper_rooms("T1", {("P", "A_I")}, plans, {"a1": "A_I"},
                               datetime.date(2026, 11, 2), "morning")
    message = str(error.value)
    assert "Rule: duty room" in message
    assert "every room in this slot has their own students" in message

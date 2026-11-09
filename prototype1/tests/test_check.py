"""Step 8 tests: the checker (check.py).

Each test makes a fresh plan from data/tiny with main.py, breaks one thing
by hand, and checks that the checker finds it and shows only the main
issue: one rule, not a flood of follow-on errors (Krish, 2026-11-05).

The tiny plan these tests break (main.py always gives the same plan):

    2026-11-02 morning  CSE2001 (with CSE2003)
                        S01: BT2CSE0001-0008    duties T001, T003
                        S02: BT2ECOM0001-0008   duties T002, T005
    2026-11-04 morning  CSE2002 in S01, ECE2001 in S02
    2026-11-06 morning  MTH2001 + PHY2002 in S01, BIO2001 in S02,
                        PHY2001 in M01

Run from prototype1/:

    python -m pytest tests
"""

import shutil
import sys
from pathlib import Path

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import check  # noqa: E402
import main  # noqa: E402

TINY = PROTOTYPE / "data" / "tiny"
SEATS = Path("daywise_seating_plans")
S01_NOV_2 = SEATS / "2026-11-02" / "morning" / "S01.csv"
S02_NOV_2 = SEATS / "2026-11-02" / "morning" / "S02.csv"
S01_NOV_6 = SEATS / "2026-11-06" / "morning" / "S01.csv"


# ------------------------------------------------------------ helpers

def make_plan(tmp_path, input_dir=TINY):
    """Run main.py on input_dir; returns the new plan folder."""
    out_root = tmp_path / "out"
    assert main.main([str(input_dir), "--output", str(out_root)]) in (0, 2)
    folders = list(out_root.iterdir())
    assert len(folders) == 1
    return folders[0]


def run_check(capsys, plan, input_dir=TINY):
    """Run check.py; returns (exit code, printed text). The main.py output
    from make_plan() is thrown away first."""
    capsys.readouterr()
    code = check.main([str(input_dir), str(plan)])
    return code, capsys.readouterr().out


def rules_named(out):
    """The rule names in a check report, e.g. {'column rule'}."""
    return {line[len("Rule: "):].rsplit(" (", 1)[0]
            for line in out.splitlines() if line.startswith("Rule: ")}


def replace_in(path, old, new):
    """Replace text that appears exactly once in a file."""
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def copy_input(tmp_path):
    """A copy of data/tiny to change."""
    folder = tmp_path / "input"
    shutil.copytree(TINY, folder)
    return folder


# ------------------------------------------------------------ clean plans

def test_clean_tiny_plan(tmp_path, capsys):
    plan = make_plan(tmp_path)
    code, out = run_check(capsys, plan)
    assert code == 0, out
    assert "no problems" in out
    assert "7 papers, 7 room files, 48 seats, 14 duties" in out


def test_clean_main_plan(tmp_path, capsys):
    main_data = PROTOTYPE / "data" / "main"
    plan = make_plan(tmp_path, main_data)
    code, out = run_check(capsys, plan, main_data)
    assert code == 0, out
    assert "510 room files" in out     # 596 before the best combination


def test_checker_writes_nothing(tmp_path, capsys):
    plan = make_plan(tmp_path)
    before = sorted(path.relative_to(plan) for path in plan.rglob("*"))
    run_check(capsys, plan)
    assert sorted(path.relative_to(plan) for path in plan.rglob("*")) == before


# ------------------------------------------------------------ seats

def test_column_rule(tmp_path, capsys):
    # BT2CSE0007 moves from column 3 to column 2, next to column 1.
    plan = make_plan(tmp_path)
    replace_in(plan / S01_NOV_2,
               "CSE2001:BT2CSE0001,,CSE2001:BT2CSE0007",
               "CSE2001:BT2CSE0001,CSE2001:BT2CSE0007,")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"column rule"}
    assert "S01.csv, columns 1 and 2: CSE2001 sits in both" in out
    assert "column 1: rows 1, 2, 3, 4, 5, 6 (BT2CSE0001," in out
    assert "column 2: row 1 (BT2CSE0007)" in out


def test_wrong_paper_in_a_cell_is_one_problem(tmp_path, capsys):
    # Krish's example: one cell says CSE2002, which is written on 4 Nov.
    # Only that cell is reported, not also "missing from CSE2001".
    plan = make_plan(tmp_path)
    replace_in(plan / S01_NOV_2, "CSE2001:BT2CSE0002", "CSE2002:BT2CSE0002")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"paper in its slot"}
    assert "1 problem(s)" in out
    assert "S01.csv row 2, column 1: CSE2002 sits here on 2026-11-02" in out


def test_student_not_in_input(tmp_path, capsys):
    # BT2CSE0099 (not a student) takes BT2CSE0002's seat. Two problems: the
    # checker can't know which missing student belonged in that seat, and
    # guessing could hide a student who really has no seat.
    plan = make_plan(tmp_path)
    replace_in(plan / S01_NOV_2, "CSE2001:BT2CSE0002", "CSE2001:BT2CSE0099")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"registration", "seated once"}
    assert "BT2CSE0099 is not a student" in out
    assert "no seat for 1 registered student(s): BT2CSE0002" in out
    assert "can't tell which missing student belonged there" in out


def test_student_seated_twice(tmp_path, capsys):
    # BT2ECOM0001 also gets the empty seat in row 3, column 3.
    plan = make_plan(tmp_path)
    replace_in(plan / S02_NOV_2, "CSE2001:BT2ECOM0003,,\n",
               "CSE2001:BT2ECOM0003,,CSE2001:BT2ECOM0001\n")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"seated once"}
    assert "BT2ECOM0001 has 2 seats" in out


def test_student_with_no_seat(tmp_path, capsys):
    plan = make_plan(tmp_path)
    replace_in(plan / S01_NOV_2, "CSE2001:BT2CSE0006", "")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"seated once"}
    assert "no seat for 1 registered student(s): BT2CSE0006" in out


def test_roll_order(tmp_path, capsys):
    # Swap BT2CSE0001 and BT2CSE0002.
    plan = make_plan(tmp_path)
    path = plan / S01_NOV_2
    text = path.read_text(encoding="utf-8")
    text = (text.replace("BT2CSE0001", "X").replace("BT2CSE0002", "BT2CSE0001")
            .replace("X", "BT2CSE0002"))
    path.write_text(text, encoding="utf-8")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"roll order"}


def test_one_paper_per_column(tmp_path, capsys):
    # PHY2002's BT2ECOM0006 moves from column 2 into column 1 (MTH2001).
    plan = make_plan(tmp_path)
    path = plan / S01_NOV_6
    replace_in(path, ",PHY2002:BT2ECOM0006,", ",,")
    replace_in(path, "\n,,\n", "\nPHY2002:BT2ECOM0006,,\n")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"one paper per column"}


# ------------------------------------------------------------ date sheet

def test_gap_rule(tmp_path, capsys):
    # The plan was made with min_gap_days 2; check it against 3.
    plan = make_plan(tmp_path)
    stricter = copy_input(tmp_path)
    replace_in(stricter / "settings.yaml", "min_gap_days: 2", "min_gap_days: 3")
    code, out = run_check(capsys, plan, stricter)
    assert code == 3
    assert rules_named(out) == {"gap"}
    assert ("CSE2001 (2026-11-02) and CSE2002 (2026-11-04) are 2 day(s) "
            "apart") in out


def test_exam_on_a_holiday(tmp_path, capsys):
    plan = make_plan(tmp_path)
    changed = copy_input(tmp_path)
    replace_in(changed / "settings.yaml", "holidays: []",
               "holidays: [2026-11-04]")
    code, out = run_check(capsys, plan, changed)
    assert code == 3
    assert rules_named(out) == {"exam days"}
    assert "CSE2002 is on 2026-11-04, a holiday" in out


def test_same_paper_codes(tmp_path, capsys):
    plan = make_plan(tmp_path)
    replace_in(plan / "schedule.csv", "CSE2001;CSE2003", "CSE2001")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"same paper"}


def test_date_moved_in_schedule_only(tmp_path, capsys):
    # The date sheet says 5 Nov but the room files say 4 Nov: one problem
    # for the paper, no follow-on gap or duty errors.
    plan = make_plan(tmp_path)
    replace_in(plan / "schedule.csv", "2026-11-04,morning,CSE2002",
               "2026-11-05,morning,CSE2002")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"paper in its slot"}
    assert "1 problem(s)" in out


# ------------------------------------------------------------ duties

def test_room_short_of_a_teacher(tmp_path, capsys):
    plan = make_plan(tmp_path)
    replace_in(plan / "duties.csv", "2026-11-02,morning,S01,T001\n", "")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"teachers per room"}
    assert "S01 on 2026-11-02 morning has 1 teacher(s) (T003)" in out


def test_teacher_in_two_rooms(tmp_path, capsys):
    plan = make_plan(tmp_path)
    replace_in(plan / "duties.csv", "2026-11-02,morning,S02,T002",
               "2026-11-02,morning,S02,T001")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"one duty per slot"}
    assert "T001 has 2 duties on 2026-11-02 morning" in out


def test_teacher_with_own_students(tmp_path, capsys):
    # T003 teaches BT2ECOM_I, T005 teaches BT2CSE_I: swap their rooms.
    plan = make_plan(tmp_path)
    path = plan / "duties.csv"
    replace_in(path, "2026-11-02,morning,S01,T003", "2026-11-02,morning,S01,X")
    replace_in(path, "2026-11-02,morning,S02,T005",
               "2026-11-02,morning,S02,T003")
    replace_in(path, "2026-11-02,morning,S01,X", "2026-11-02,morning,S01,T005")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"own students"}
    assert "T003 is in S02 on 2026-11-02 morning, with their own students" in out


def test_teacher_without_own_paper_duty(tmp_path, capsys):
    # T003 teaches CSE2001; the PhD scholar T009 takes their place.
    plan = make_plan(tmp_path)
    replace_in(plan / "duties.csv", "2026-11-02,morning,S01,T003",
               "2026-11-02,morning,S01,T009")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"own paper duty"}
    assert "T003 teaches CSE2001 (2026-11-02 morning)" in out


def test_duty_in_an_unused_room(tmp_path, capsys):
    plan = make_plan(tmp_path)
    with open(plan / "duties.csv", "a", encoding="utf-8") as file:
        file.write("2026-11-02,morning,M01,T009\n")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"duty in a used room"}


def test_unknown_teacher(tmp_path, capsys):
    plan = make_plan(tmp_path)
    replace_in(plan / "duties.csv", "2026-11-02,morning,S01,T001",
               "2026-11-02,morning,S01,T999")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"known teacher"}


# ------------------------------------------------------------ stage 1: files

def test_room_csv_with_a_row_missing(tmp_path, capsys):
    plan = make_plan(tmp_path)
    path = plan / S01_NOV_2
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:-1]), encoding="utf-8")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"room shape"}
    assert "Fix these first" in out


def test_bad_cell(tmp_path, capsys):
    plan = make_plan(tmp_path)
    replace_in(plan / S01_NOV_2, "CSE2001:BT2CSE0002", "CSE2001-BT2CSE0002")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"room cell"}


def test_extra_file_in_plan_folder(tmp_path, capsys):
    plan = make_plan(tmp_path)
    (plan / "notes.txt").write_text("hello", encoding="utf-8")
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"output files"}


def test_missing_duties_csv(tmp_path, capsys):
    plan = make_plan(tmp_path)
    (plan / "duties.csv").unlink()
    code, out = run_check(capsys, plan)
    assert code == 3
    assert rules_named(out) == {"output files"}
    assert "duties.csv is missing" in out


# ------------------------------------------------------------ exit 1 and 2

def test_no_plan_folder_gives_exit_2(tmp_path, capsys):
    impossible = PROTOTYPE / "data" / "impossible" / "too_few_teachers"
    plan = make_plan(tmp_path, impossible)
    code, out = run_check(capsys, plan, impossible)
    assert code == 2
    assert "No plan in this folder" in out
    assert "Rule: duties" in out


def test_missing_input_folder_gives_exit_1(tmp_path, capsys):
    plan = make_plan(tmp_path)
    code, out = run_check(capsys, plan, tmp_path / "nothing")
    assert code == 1
    assert out.startswith("Can't check:")


def test_missing_rooms_csv_gives_exit_1(tmp_path, capsys):
    plan = make_plan(tmp_path)
    changed = copy_input(tmp_path)
    (changed / "rooms.csv").unlink()
    code, out = run_check(capsys, plan, changed)
    assert code == 1
    assert "rooms.csv is missing" in out


def test_missing_plan_folder_gives_exit_1(tmp_path, capsys):
    code, out = run_check(capsys, tmp_path / "no_plan_here")
    assert code == 1
    assert "plan folder" in out

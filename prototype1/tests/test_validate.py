"""Step 3 tests: break data/tiny on purpose and check the right error comes out.

Run from prototype1/:

    python -m pytest tests
"""

import shutil
import sys
from pathlib import Path

import pytest

PROTOTYPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROTOTYPE))

import main  # noqa: E402


@pytest.fixture
def tiny(tmp_path):
    """A fresh copy of data/tiny that a test may break."""
    folder = tmp_path / "tiny"
    shutil.copytree(PROTOTYPE / "data" / "tiny", folder)
    return folder


def run(folder, capsys, output=None):
    """Run main.py on a folder. Returns (exit code, printed text).
    A valid folder now writes a plan, so pass output= (a temporary folder)
    to keep it out of prototype1/output/."""
    argv = [str(folder)]
    if output is not None:
        argv += ["--output", str(output)]
    code = main.main(argv)
    return code, capsys.readouterr().out


def append_line(path, line):
    with open(path, "a", encoding="utf-8") as file:
        file.write(line + "\n")


def replace_text(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"test setup: {old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------- valid input

@pytest.mark.parametrize("dataset", ["tiny", "main"])
def test_generated_datasets_are_valid(dataset, tmp_path, capsys):
    code, out = run(PROTOTYPE / "data" / dataset, capsys, output=tmp_path)
    assert code == 0, out
    assert out.startswith("Input OK")


# ---------------------------------------------------------------- stage 1

def test_missing_input_folder(tmp_path, capsys):
    code, out = run(tmp_path / "nope", capsys)
    assert code == 1
    assert "folder not found" in out


def test_missing_file(tiny, capsys):
    (tiny / "rooms.csv").unlink()
    code, out = run(tiny, capsys)
    assert code == 1
    assert "rooms.csv: file is missing" in out


def test_bad_header_gives_one_error_not_a_flood(tiny, capsys):
    replace_text(tiny / "sections.csv", "section_id", "sectoin_id")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "Input is invalid: 1 problem(s)" in out
    assert "sections.csv row 1: header should be" in out


def test_row_with_too_few_values(tiny, capsys):
    append_line(tiny / "rooms.csv", "S99,S,6")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "has 3 value(s), expected 4" in out


def test_broken_yaml(tiny, capsys):
    (tiny / "settings.yaml").write_text("start_date: [2026-11-02\n")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "settings.yaml: cannot be read as YAML" in out


# ---------------------------------------------------------------- stage 2

def test_unknown_course_code_names_the_row(tiny, capsys):
    append_line(tiny / "registrations.csv", "BT2CSE0001,CSE9999")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "registrations.csv row 50: course code CSE9999 is not in courses.csv" in out


def test_errors_are_grouped_with_a_count(tiny, capsys):
    append_line(tiny / "registrations.csv", "BT2CSE0001,CSE9998")
    append_line(tiny / "registrations.csv", "BT2CSE0002,CSE9999")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "[course code exists] 2 problem(s)" in out
    assert "CSE9998" in out and "CSE9999" in out  # every problem still listed


def test_duplicate_id(tiny, capsys):
    append_line(tiny / "rooms.csv", "S01,M,7,6")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "room_id S01 is already used in row 2" in out


def test_student_in_two_sections(tiny, capsys):
    append_line(tiny / "sections" / "BT2ECOM_I.csv", "BT2CSE0001")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "student BT2CSE0001 is already in sections/BT2CSE_I.csv row 2" in out


def test_student_with_no_registrations(tiny, capsys):
    append_line(tiny / "sections" / "BT2CSE_I.csv", "BT2CSE0099")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "student BT2CSE0099 has no registrations" in out


def test_registration_for_another_cohort(tiny, capsys):
    append_line(tiny / "registrations.csv", "BT2CSE0001,ECE2001")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "BT2CSE0001 is in cohort BT2CSE, but ECE2001 is offered to BT2ECOM" in out


def test_course_with_no_students(tiny, capsys):
    append_line(tiny / "courses.csv", "CSE2099,Empty Course,BT2CSE,ELECTIVE")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "nobody is registered for CSE2099, so it has no exam" in out


def test_teaching_a_section_with_no_students_for_it(tiny, capsys):
    # PHY2002 is a BT2ECOM elective; add a second BT2ECOM section with one
    # student who does not take it, then say someone teaches it there.
    append_line(tiny / "sections.csv", "BT2ECOM_II,BT2ECOM,BTECH,2")
    (tiny / "sections" / "BT2ECOM_II.csv").write_text(
        "student_id\nBT2ECOM0099\n")
    append_line(tiny / "registrations.csv", "BT2ECOM0099,ECE2001")
    append_line(tiny / "teaching.csv", "T001,PHY2002,BT2ECOM_II")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "no student of BT2ECOM_II is registered for PHY2002" in out


def test_bad_room_and_rank_values(tiny, capsys):
    append_line(tiny / "rooms.csv", "L01,L,abc,6")
    append_line(tiny / "teachers.csv", "T999,DEAN")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "type of L01 is L" in out
    assert "rows of L01 is abc" in out
    assert "rank of T999 is DEAN" in out


def test_bad_settings(tiny, capsys):
    replace_text(tiny / "settings.yaml", "start_date: 2026-11-02",
                 "start_date: 2026-11-30")
    replace_text(tiny / "settings.yaml", "[morning, evening]",
                 "[morning, afternoon, evening]")
    replace_text(tiny / "settings.yaml", "min_gap_days: 2", "min_gap_days: 0")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "start_date 2026-11-30 is after end_date 2026-11-06" in out
    assert "sessions should be two different names" in out
    assert "min_gap_days should be a whole number of at least 1" in out


def test_bad_constraints(tiny, capsys):
    (tiny / "constraints.yaml").write_text(
        "same_paper:\n"
        "- [CSE2001, CSE2003]\n"
        "- [CSE2003, CSE9999]\n"
        "- [PHY2001]\n")
    code, out = run(tiny, capsys)
    assert code == 1
    assert "same_paper group 2: CSE2003 is also in same_paper group 1" in out
    assert "same_paper group 2: course code CSE9999 is not in courses.csv" in out
    assert "same_paper group 3 ['PHY2001'] has 1 code(s)" in out

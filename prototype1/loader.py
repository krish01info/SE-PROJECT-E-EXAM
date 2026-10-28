"""Read an input folder into plain Python data.

This module only READS. It does not decide whether the data is right;
that is validate.py's job. Run validate.check_files() first: load() assumes
every file exists and every header is right.

What load() gives back is one dict:

    data["sections"]       rows of sections.csv
    data["courses"]        rows of courses.csv
    data["registrations"]  rows of registrations.csv
    data["rooms"]          rows of rooms.csv
    data["teachers"]       rows of teachers.csv
    data["teaching"]       rows of teaching.csv
    data["students"]       one row per line of every sections/<section>.csv,
                           with the section ID added
    data["roster_files"]   section IDs that have a file in sections/
    data["settings"]       settings.yaml as a dict
    data["constraints"]    constraints.yaml as a dict

A "row" is a dict of column -> value, plus "_row": the line number in the
file, counting the header as row 1 (the same number a spreadsheet shows).
"""

import csv
from pathlib import Path

import yaml

# File name -> the exact header it must have (data_design_spec.md section 2)
CSV_COLUMNS = {
    "sections.csv": ["section_id", "cohort_id", "program", "year"],
    "courses.csv": ["course_code", "title", "cohort_id", "kind"],
    "registrations.csv": ["student_id", "course_code"],
    "rooms.csv": ["room_id", "type", "rows", "seat_columns"],
    "teachers.csv": ["teacher_id", "rank"],
    "teaching.csv": ["teacher_id", "course_code", "section_id"],
}
ROSTER_FOLDER = "sections"
ROSTER_COLUMNS = ["student_id"]
YAML_FILES = ["settings.yaml", "constraints.yaml"]


def read_csv_lines(path):
    """Read a CSV file. Returns (header, rows).

    header is a list of column names. rows is a list of
    (row_number, values). Spaces around values are removed, fully blank
    lines are skipped, and a byte-order mark (added by Excel) is ignored.
    """
    header = []
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        for values in reader:
            values = [value.strip() for value in values]
            if not any(values):
                continue  # blank line
            if not header:
                header = values
            else:
                rows.append((reader.line_num, values))
    return header, rows


def read_table(path):
    """Read a CSV file into a list of row dicts (see the module docstring)."""
    header, rows = read_csv_lines(path)
    return [dict(zip(header, values), _row=number) for number, values in rows]


def read_yaml(path):
    """Read a YAML file. An empty file gives an empty dict."""
    with open(path, encoding="utf-8-sig") as file:
        content = yaml.safe_load(file)
    return content if content is not None else {}


def roster_paths(input_dir):
    """All section roster files, sorted by name so the order never changes."""
    return sorted((Path(input_dir) / ROSTER_FOLDER).glob("*.csv"))


def load(input_dir):
    """Read every file of an input folder. See the module docstring."""
    input_dir = Path(input_dir)
    data = {}
    for file_name in CSV_COLUMNS:
        table_name = file_name.removesuffix(".csv")
        data[table_name] = read_table(input_dir / file_name)

    data["students"] = []
    data["roster_files"] = []
    for path in roster_paths(input_dir):
        section_id = path.stem
        data["roster_files"].append(section_id)
        for row in read_table(path):
            row["section_id"] = section_id
            row["_file"] = f"{ROSTER_FOLDER}/{path.name}"
            data["students"].append(row)

    data["settings"] = read_yaml(input_dir / "settings.yaml")
    data["constraints"] = read_yaml(input_dir / "constraints.yaml")
    return data

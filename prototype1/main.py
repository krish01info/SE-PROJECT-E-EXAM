"""Prototype1 exam planner: command line entry point (model spec section 4).

Run from prototype1/:

    python main.py data/tiny

Exit codes (model spec section 4):
    0  a plan was written (right now: schedule.csv only)
    1  the input is invalid; every problem is printed
    2  no plan is possible; the reason is printed and nothing is written

Built so far: step 3 (load and validate) and step 4 (schedule).
Seating (step 5) and duties (step 6) come next.
"""

import argparse
import csv
import datetime
import sys
from pathlib import Path

import loader
import schedule
import validate

SCHEDULE_COLUMNS = ["date", "session", "paper_id", "course_codes", "students"]


def summary(data):
    """One line with the sizes of a valid input folder."""
    groups = data["constraints"].get("same_paper") or []
    papers = len(data["courses"]) - sum(len(group) - 1 for group in groups)
    return (f"Input OK: {len(data['sections'])} sections, "
            f"{len(data['students'])} students, "
            f"{len(data['courses'])} course codes ({papers} papers), "
            f"{len(data['rooms'])} rooms, {len(data['teachers'])} teachers.")


def make_output_folder(output_root):
    """A new folder named by the time of the run (model spec section 11).
    If two runs start in the same second, the second one gets _2, _3, ..."""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = Path(output_root) / stamp
    number = 2
    while folder.exists():
        folder = Path(output_root) / f"{stamp}_{number}"
        number += 1
    folder.mkdir(parents=True)
    return folder


def write_schedule(placements, path):
    """schedule.csv: one row per paper. Course codes of one paper are joined
    with ';' so the cell needs no quotes."""
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SCHEDULE_COLUMNS)
        for placement in placements:
            paper = placement.paper
            writer.writerow([placement.date.isoformat(), placement.session,
                             paper.paper_id, ";".join(paper.course_codes),
                             len(paper.students)])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Turn an input folder into an exam plan.")
    parser.add_argument("input_dir", help="folder with the input files")
    parser.add_argument("--output", default="output",
                        help="where plan folders go (default: output/)")
    args = parser.parse_args(argv)

    # Stage 1: are the files there and readable?
    problems = validate.check_files(args.input_dir)
    if problems:
        print(validate.format_report(problems))
        print("\nFix these first. The checks on the data inside the files "
              "run once every file can be read.")
        return 1

    # Stage 2: is the data inside the files right?
    data = loader.load(args.input_dir)
    problems = validate.check_data(data)
    if problems:
        print(validate.format_report(problems))
        return 1
    print(summary(data))

    # Step 4: papers to dates and sessions.
    try:
        placements = schedule.make_schedule(data)
    except schedule.NoPlan as reason:
        print(reason)
        return 2

    if not placements:
        print("No papers to schedule: courses.csv has no course codes.")
        return 2

    folder = make_output_folder(args.output)
    write_schedule(placements, folder / "schedule.csv")

    days = sorted({placement.date for placement in placements})
    print(f"Scheduled {len(placements)} papers on {len(days)} days, "
          f"{days[0]} to {days[-1]}.")
    fullest = schedule.fullest_session(placements, data)
    if fullest:
        day, session, students, seat_limit = fullest
        print(f"Fullest session: {day} {session}, {students} of {seat_limit} "
              f"seats ({seat_limit - students} left).")
    print(f"Wrote {folder / 'schedule.csv'}")
    print("Seating (step 5) and duties (step 6) are not built yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

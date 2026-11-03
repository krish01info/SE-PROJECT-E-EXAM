"""Prototype1 exam planner: command line entry point (model spec section 4).

Run from prototype1/:

    python main.py data/tiny

Exit codes (model spec section 4):
    0  a plan was written (right now: schedule.csv and the room CSVs)
    1  the input is invalid; every problem is printed
    2  no plan is possible; the reason is printed and nothing is written

Built so far: step 3 (load and validate), step 4 (schedule) and
step 5 (seat). Duties (step 6) come next.
"""

import argparse
import csv
import datetime
import sys
from pathlib import Path

import duties
import loader
import schedule
import seat
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


def write_seating(seating, folder):
    """One CSV per room in use per slot (model spec section 11):
    daywise_seating_plans/<date>/<session>/<room_id>.csv. No header row:
    each CSV row is a row of seats, front first. Returns the file count."""
    count = 0
    for (day, session), room_plans in seating.items():
        slot_folder = folder / "daywise_seating_plans" / day.isoformat() / session
        slot_folder.mkdir(parents=True, exist_ok=True)
        for room_plan in room_plans:
            path = slot_folder / f"{room_plan.room_id}.csv"
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                for row in room_plan.grid:
                    writer.writerow([seat.cell_text(cell) for cell in row])
            count += 1
    return count


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

    # Step 5: students to seats. Done before anything is written, so a
    # failed seating leaves no half-written plan.
    try:
        seating = seat.make_seating(placements, data["rooms"],
                                    duties.section_of_student(data))
    except schedule.NoPlan as reason:
        print(reason)
        return 2

    folder = make_output_folder(args.output)
    write_schedule(placements, folder / "schedule.csv")
    room_files = write_seating(seating, folder)

    days = sorted({placement.date for placement in placements})
    print(f"Scheduled {len(placements)} papers on {len(days)} days, "
          f"{days[0]} to {days[-1]}.")
    fullest = schedule.fullest_session(placements, data)
    if fullest:
        day, session, students, seat_limit = fullest
        print(f"Fullest session: {day} {session}, {students} of {seat_limit} "
              f"seats ({seat_limit - students} left).")
    busiest = max(seating.items(), key=lambda item: len(item[1]))
    two_paper = sum(1 for plans in seating.values()
                    for plan in plans if len(plan.papers) == 2)
    print(f"Seating: {room_files} room files ({two_paper} with two papers). "
          f"Most rooms in one slot: {len(busiest[1])} of {len(data['rooms'])}"
          f" ({busiest[0][0]} {busiest[0][1]}).")
    print(f"Wrote {folder}")
    print("Duties (step 6) are not built yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

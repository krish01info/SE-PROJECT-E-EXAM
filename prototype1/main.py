"""Prototype1 exam planner: command line entry point (model spec section 4).

Run from prototype1/:

    python main.py data/tiny

Exit codes (model spec section 4):
    0  the input is valid (from step 4 on: a plan was written)
    1  the input is invalid; every problem is printed
    2  no plan is possible (from step 7 on)

Right now (step 3) the tool only loads and validates the input.
"""

import argparse
import sys

import loader
import validate


def summary(data):
    """One line with the sizes of a valid input folder."""
    groups = data["constraints"].get("same_paper") or []
    papers = len(data["courses"]) - sum(len(group) - 1 for group in groups)
    return (f"Input OK: {len(data['sections'])} sections, "
            f"{len(data['students'])} students, "
            f"{len(data['courses'])} course codes ({papers} papers), "
            f"{len(data['rooms'])} rooms, {len(data['teachers'])} teachers.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Turn an input folder into an exam plan.")
    parser.add_argument("input_dir", help="folder with the input files")
    parser.add_argument("--output", default="output",
                        help="where plan folders go (default: output/); "
                             "used from step 4 on")
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
    print("Scheduling is not built yet (step 4).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

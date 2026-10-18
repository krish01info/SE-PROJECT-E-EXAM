from __future__ import annotations

import argparse
from pathlib import Path

from validation import validate_input


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Prototype 1 exam plan from an input folder.")
    parser.add_argument("input_dir", type=Path, help="Folder containing the Prototype 1 input files.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output root used by later build steps (default: output/).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_input(args.input_dir)

    if not result.valid:
        print("Input invalid.")
        for error in result.errors:
            print(f"- {error}")
        return 1

    print("Input valid.")
    print(
        f"{result.students} students, "
        f"{result.course_codes} course codes, "
        f"{result.rooms} rooms, "
        f"{result.invigilators} invigilators."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

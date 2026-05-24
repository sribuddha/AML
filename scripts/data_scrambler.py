"""Shuffle all data rows in a CSV file in-place (header preserved, rows randomized)."""

import argparse
import csv
import random
from pathlib import Path


def scramble(path: Path):
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return

    with open(path, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print(f"ERROR: Empty file: {path}")
            return
        rows = list(reader)

    random.shuffle(rows)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Scrambled {len(rows)} rows in {path}")


def main():
    parser = argparse.ArgumentParser(description="Shuffle CSV rows in-place")
    parser.add_argument("path", type=str, help="Path to CSV file")
    args = parser.parse_args()
    scramble(Path(args.path))


if __name__ == "__main__":
    main()

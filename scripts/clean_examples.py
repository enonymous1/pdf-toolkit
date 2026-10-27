"""Remove generated artifacts under examples/*/outputs/ (keeps .gitkeep).

Usage: python scripts/clean_examples.py [--dry-run]
"""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean generated example outputs")
    parser.add_argument("--dry-run", action="store_true", help="Show files that would be removed")
    args = parser.parse_args()

    root = Path("examples")
    removed = []
    for out_dir in root.glob("**/outputs"):
        for p in out_dir.iterdir():
            if p.name == ".gitkeep":
                continue
            if p.is_file():
                removed.append(p)

    if args.dry_run:
        for p in removed:
            print(p)
    else:
        for p in removed:
            try:
                p.unlink()
                print("Removed:", p)
            except Exception as e:
                print("Failed to remove", p, e)


if __name__ == "__main__":
    main()

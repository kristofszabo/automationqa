from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phases import phase4_review


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="automationqa — step review UI")
    p.add_argument("--steps", type=Path, help="Path to steps.json (default: <workdir>/steps.json)")
    p.add_argument("--workdir", default="output", type=Path, help="Working directory (default: output)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    workdir = args.workdir.resolve()
    steps_path = args.steps.resolve() if args.steps else workdir / "steps.json"

    if not steps_path.exists():
        print(f"Error: steps.json not found: {steps_path}", file=sys.stderr)
        return 1

    phase4_review.run(steps_path=steps_path, output_dir=workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

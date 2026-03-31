from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from phases import phase5_generate


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="automationqa — Phase 5: test generation")
    p.add_argument("--workdir", default="output", type=Path, help="Working directory (default: output)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    workdir = args.workdir.resolve()
    steps_path = workdir / "steps.json"

    if not steps_path.exists():
        print(f"Error: steps.json not found in {workdir}", file=sys.stderr)
        return 1

    phase5_generate.run(steps_path=steps_path, output_dir=workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

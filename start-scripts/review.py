from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from phases import phase4_review


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "automationqa — Phase 4: Step review UI\n"
            "Starts a local Flask server with a React UI to review and edit the detected steps.\n"
            "Input:  <workdir>/steps.json\n"
            "Output: updated <workdir>/steps.json (saved on approve)\n"
            "\n"
            "Opens the browser automatically on http://localhost:5000"
        ),
        epilog=(
            "examples:\n"
            "  npm run phase4\n"
            "  npm run phase4 -- --workdir output\n"
            "  npm run phase4 -- --steps path/to/steps.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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

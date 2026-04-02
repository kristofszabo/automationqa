from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from phases import phase5_generate


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "automationqa — Phase 5: Test generation\n"
            "Uses Gemini to generate a Playwright TypeScript test from steps.json.\n"
            "Validates with tsc, retries once on error.\n"
            "Input:  <workdir>/steps.json\n"
            "Output: <workdir>/test_generated.spec.ts\n"
            "\n"
            "Required env var: GEMINI_API_KEY\n"
            "Optional env var: GEMINI_MODEL (default: gemini-2.5-flash-lite)"
        ),
        epilog=(
            "examples:\n"
            "  npm run phase5\n"
            "  npm run phase5 -- --workdir output"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--workdir", default="output", type=Path, help="Working directory containing steps.json (default: output)")
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

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from phases import phase3_analyze


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "automationqa — Phase 3: Vision analysis\n"
            "Sends extracted frames to Gemini Vision API to identify UI interactions.\n"
            "Input:  <workdir>/manifest.json\n"
            "Output: <workdir>/steps.json\n"
            "\n"
            "Required env var: GEMINI_API_KEY\n"
            "Optional env var: GEMINI_MODEL (default: gemini-2.5-flash-lite)"
        ),
        epilog=(
            "examples:\n"
            "  npm run phase3\n"
            "  npm run phase3 -- --workdir output"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--workdir", default="output", type=Path, help="Working directory containing manifest.json (default: output)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    workdir = args.workdir.resolve()
    manifest_path = workdir / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: manifest.json not found in {workdir}", file=sys.stderr)
        return 1

    phase3_analyze.run(manifest_path=manifest_path, output_dir=workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

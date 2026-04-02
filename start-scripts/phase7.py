from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from phases import phase7_refine


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "automationqa — Phase 7: Gemini test re-generation\n"
            "Reads the Phase 6 run results (pass/fail output + DOM snapshots) and uses Gemini\n"
            "to generate an improved final test. Validates with tsc, retries once on error.\n"
            "Input:  <workdir>/run_results.json  +  <workdir>/test_generated.spec.ts\n"
            "Output: <workdir>/test_final.spec.ts\n"
            "\n"
            "Required env var: GEMINI_API_KEY\n"
            "Optional env var: GEMINI_MODEL (default: gemini-2.5-flash-lite)\n"
            "\n"
            "Note: run phase6 first to generate run_results.json"
        ),
        epilog=(
            "examples:\n"
            "  npm run phase7\n"
            "  npm run phase7 -- --workdir output\n"
            "  npm run phase7 -- --test output/test_generated.spec.ts --results output/run_results.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--workdir", default="output", type=Path, help="Working directory (default: output)")
    p.add_argument("--test", default=None, type=Path, help="Spec file to refine (default: <workdir>/test_generated.spec.ts)")
    p.add_argument("--results", default=None, type=Path, help="Path to run_results.json from phase6 (default: <workdir>/run_results.json)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    workdir = args.workdir.resolve()
    test_path = (args.test or workdir / "test_generated.spec.ts").resolve()
    results_path = (args.results or workdir / "run_results.json").resolve()

    if not test_path.exists():
        print(f"Error: test file not found: {test_path}", file=sys.stderr)
        return 1
    if not results_path.exists():
        print(f"Error: run_results.json not found: {results_path}", file=sys.stderr)
        print("Run phase6 first.", file=sys.stderr)
        return 1

    phase7_refine.run(run_results_path=results_path, test_path=test_path, output_dir=workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

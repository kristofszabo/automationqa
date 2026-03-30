from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phases import phase3_analyze


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="automationqa — Phase 3: vision analysis")
    p.add_argument("--workdir", default="output", type=Path, help="Working directory (default: output)")
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

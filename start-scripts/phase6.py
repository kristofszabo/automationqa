from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from phases import phase6_run


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "automationqa — Phase 6: Step replay + DOM snapshot\n"
            "Replays steps from steps.json in a browser and captures DOM snapshots\n"
            "after each action. Results are saved for Phase 7 to use.\n"
            "Input:  <workdir>/steps.json\n"
            "Output: <workdir>/run_results.json  +  <workdir>/snapshots_phase6/\n"
            "\n"
            "Auth/URL config can be set via <workdir>/config.json:\n"
            '  { "base_url": "https://myapp.com", "storage_state": "output/auth.json" }'
        ),
        epilog=(
            "examples:\n"
            "  npm run phase6\n"
            "  npm run phase6 -- --headed\n"
            "  npm run phase6 -- --headed --video --trace\n"
            "  npm run phase6 -- --base-url https://myapp.com\n"
            "  npm run phase6 -- --storage-state output/auth.json\n"
            "\n"
            "view trace:\n"
            "  npx playwright show-trace output/trace_phase6.zip"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--workdir", default="output", type=Path, help="Working directory (default: output)")
    p.add_argument("--headed", action="store_true", help="Run browser in headed (visible) mode")
    p.add_argument("--video", action="store_true", help="Record video (saved to <workdir>/videos_phase6/)")
    p.add_argument("--trace", action="store_true", help="Record Playwright trace (saved to <workdir>/trace_phase6.zip)")
    p.add_argument("--base-url", default=None, help="Base URL to navigate to if steps.json has no navigate action (overrides config.json)")
    p.add_argument("--storage-state", default=None, type=Path, help="Playwright auth state JSON with cookies/localStorage (overrides config.json)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    workdir = args.workdir.resolve()
    steps_path = workdir / "steps.json"

    if not steps_path.exists():
        print(f"Error: steps.json not found in {workdir}", file=sys.stderr)
        return 1

    config = phase6_run.load_config(workdir)
    base_url: str | None = args.base_url or config.get("base_url") or None
    storage_state_raw: str | None = str(args.storage_state) if args.storage_state else config.get("storage_state")
    storage_state = Path(storage_state_raw) if storage_state_raw else None

    phase6_run.run(
        steps_path=steps_path,
        output_dir=workdir,
        headless=not args.headed,
        video=args.video,
        trace=args.trace,
        base_url=base_url,
        storage_state=storage_state,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

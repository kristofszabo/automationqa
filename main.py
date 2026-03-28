from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phases import phase2_extract, phase3_analyze


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="automationqa — screen recording → Playwright test")
    p.add_argument("--video", required=True, type=Path, help="Path to the screen recording")
    p.add_argument("--workdir", default="output", type=Path, help="Working directory for artifacts")
    p.add_argument("--fps", type=int, default=2, help="Frames per second to extract (default: 2)")
    p.add_argument("--phash-threshold", type=int, default=8, dest="phash_threshold",
                   help="pHash hamming distance below which frames are dropped (default: 8)")
    p.add_argument("--mad-threshold", type=float, default=0.003, dest="mad_threshold",
                   help="Region MAD max below which frames are dropped (default: 0.003)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    video_path: Path = args.video.resolve()
    workdir: Path = args.workdir.resolve()

    if not video_path.exists():
        print(f"Error: video file not found: {video_path}", file=sys.stderr)
        return 1

    workdir.mkdir(parents=True, exist_ok=True)

    # Phase 2 — Frame Extraction
    manifest = phase2_extract.run(
        video_path=video_path,
        output_dir=workdir,
        fps=args.fps,
        phash_threshold=args.phash_threshold,
        mad_threshold=args.mad_threshold,
    )

    # Phase 3 — Vision Analysis (skeleton)
    manifest_path = workdir / "manifest.json"
    phase3_analyze.run(manifest_path=manifest_path, output_dir=workdir)

    return 0


if __name__ == "__main__":
    sys.exit(main())

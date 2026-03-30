from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phases import phase2_extract


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="automationqa — Phase 2: frame extraction")
    p.add_argument("--video", required=True, type=Path, help="Path to the screen recording")
    p.add_argument("--workdir", default="output", type=Path, help="Working directory (default: output)")
    p.add_argument("--fps", type=int, default=2, help="Frames per second to extract (default: 2)")
    p.add_argument("--phash-threshold", type=int, default=8, dest="phash_threshold")
    p.add_argument("--mad-threshold", type=float, default=0.003, dest="mad_threshold")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    video_path = args.video.resolve()
    workdir = args.workdir.resolve()

    if not video_path.exists():
        print(f"Error: video file not found: {video_path}", file=sys.stderr)
        return 1

    workdir.mkdir(parents=True, exist_ok=True)
    phase2_extract.run(
        video_path=video_path,
        output_dir=workdir,
        fps=args.fps,
        phash_threshold=args.phash_threshold,
        mad_threshold=args.mad_threshold,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

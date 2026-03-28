from __future__ import annotations

import subprocess
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

from models.manifest import FrameEntry, Manifest


def extract_frames(video_path: Path, output_dir: Path, fps: int = 2) -> list[Path]:
    """Run ffmpeg to extract frames at the given fps. Returns sorted list of PNG paths."""
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        str(frames_dir / "frame_%06d.png"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")

    return sorted(frames_dir.glob("frame_*.png"))


def _phash(img: Image.Image) -> imagehash.ImageHash:
    return imagehash.phash(img)


def _region_mad_max(prev: np.ndarray, curr: np.ndarray, grid: int = 3) -> float:
    """Split both images into grid×grid cells, return max normalised MAD across cells."""
    h, w = prev.shape[:2]
    cell_h, cell_w = h // grid, w // grid
    max_mad = 0.0
    for r in range(grid):
        for c in range(grid):
            p = prev[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
            q = curr[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
            mad = float(np.abs(p.astype(float) - q.astype(float)).mean() / 255)
            if mad > max_mad:
                max_mad = mad
    return max_mad


def deduplicate(
    frame_paths: list[Path],
    phash_threshold: int = 8,
    mad_threshold: float = 0.003,
) -> list[tuple[Path, float | None]]:
    """Return (path, diff_score) for frames that should be kept.

    Two-level filter:
      1. pHash hamming distance < phash_threshold → identical, drop
      2. Region MAD max < mad_threshold → still too similar, drop
    The first frame is always kept.
    """
    if not frame_paths:
        return []

    kept: list[tuple[Path, float | None]] = []
    prev_img = Image.open(frame_paths[0]).convert("RGB")
    prev_arr = np.array(prev_img)
    prev_hash = _phash(prev_img)
    kept.append((frame_paths[0], None))

    for path in frame_paths[1:]:
        curr_img = Image.open(path).convert("RGB")
        curr_hash = _phash(curr_img)

        hamming = prev_hash - curr_hash
        if hamming < phash_threshold:
            # Level 1: perceptually identical — drop
            continue

        curr_arr = np.array(curr_img)
        mad = _region_mad_max(prev_arr, curr_arr)
        if mad < mad_threshold:
            # Level 2: small region change still below threshold — drop
            continue

        kept.append((path, round(mad, 6)))
        prev_img = curr_img
        prev_arr = curr_arr
        prev_hash = curr_hash

    return kept


def build_manifest(
    kept: list[tuple[Path, float | None]],
    video_path: Path,
    fps: int,
) -> Manifest:
    ms_per_frame = 1000 // fps
    frames = []
    for idx, (path, diff_score) in enumerate(kept):
        # Derive original frame number from filename (frame_000001.png → 1)
        frame_num = int(path.stem.split("_")[1])
        timestamp_ms = (frame_num - 1) * ms_per_frame
        frames.append(FrameEntry(
            index=idx,
            path=str(path),
            timestamp_ms=timestamp_ms,
            diff_score=diff_score,
        ))
    return Manifest(video=str(video_path), fps_extracted=fps, frames=frames)


def run(
    video_path: Path,
    output_dir: Path,
    fps: int = 2,
    phash_threshold: int = 8,
    mad_threshold: float = 0.003,
) -> Manifest:
    print(f"[Phase 2] Extracting frames from {video_path.name} at {fps}fps…")
    all_frames = extract_frames(video_path, output_dir, fps)
    print(f"[Phase 2] Extracted {len(all_frames)} frames, deduplicating…")

    kept = deduplicate(all_frames, phash_threshold, mad_threshold)
    dropped = len(all_frames) - len(kept)
    print(f"[Phase 2] Kept {len(kept)} frames, dropped {dropped} duplicates")

    manifest = build_manifest(kept, video_path, fps)
    manifest_path = output_dir / "manifest.json"
    manifest.save(manifest_path)
    print(f"[Phase 2] Manifest written → {manifest_path}")
    return manifest

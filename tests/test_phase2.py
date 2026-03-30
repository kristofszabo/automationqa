"""Tests for Phase 2 — frame extraction and deduplication."""
from __future__ import annotations

from pathlib import Path

import pytest

from phases.phase2_extract import build_manifest, deduplicate
from tests.conftest import make_frame


def _frames(frames_dir: Path, specs: list[tuple[int, str]]) -> list[Path]:
    paths = []
    for num, variant in specs:
        p = frames_dir / f"frame_{num:06d}.png"
        make_frame(p, variant)
        paths.append(p)
    return paths


class TestDeduplicate:
    def test_identical_frames_dropped(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank"), (2, "blank"), (3, "blank")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        assert len(kept) == 1

    def test_different_frames_all_kept(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank"), (2, "modal"), (3, "typed")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        assert len(kept) == 3

    def test_first_frame_always_kept(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        assert len(kept) == 1
        assert str(paths[0]) in {str(p) for p, _ in kept}

    def test_small_region_change_kept(self, frames_dir: Path) -> None:
        """Toast frame has a small region change that pHash misses but MAD catches."""
        paths = _frames(frames_dir, [
            (1, "blank"),
            (2, "blank"),   # dropped
            (3, "toast"),   # small corner change — must be kept
        ])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        kept_paths = {str(p) for p, _ in kept}
        assert str(paths[2]) in kept_paths

    def test_duplicate_after_change_dropped(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [
            (1, "blank"),
            (2, "modal"),   # kept
            (3, "modal"),   # duplicate — dropped
        ])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        assert len(kept) == 2

    def test_returns_diff_scores(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank"), (2, "modal")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        # First frame has no predecessor, score is None
        assert kept[0][1] is None
        # Second frame has a diff score
        assert isinstance(kept[1][1], float)


class TestBuildManifest:
    def test_manifest_frame_count(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank"), (2, "modal")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        manifest = build_manifest(kept, video_path=Path("test.mp4"), fps=2)
        assert len(manifest.frames) == 2

    def test_manifest_video_field(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        manifest = build_manifest(kept, video_path=Path("myvideo.mp4"), fps=2)
        assert manifest.video == "myvideo.mp4"

    def test_manifest_fps_field(self, frames_dir: Path) -> None:
        paths = _frames(frames_dir, [(1, "blank")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        manifest = build_manifest(kept, video_path=Path("v.mp4"), fps=5)
        assert manifest.fps_extracted == 5

    def test_manifest_save_and_load(self, frames_dir: Path, tmp_path: Path) -> None:
        from models.manifest import Manifest

        paths = _frames(frames_dir, [(1, "blank"), (2, "modal")])
        kept = deduplicate(paths, phash_threshold=8, mad_threshold=0.003)
        manifest = build_manifest(kept, video_path=Path("v.mp4"), fps=2)

        out = tmp_path / "manifest.json"
        manifest.save(out)
        loaded = Manifest.load(out)

        assert len(loaded.frames) == len(manifest.frames)
        assert loaded.video == manifest.video

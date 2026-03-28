"""Smoke test — runs Phase 2 dedup + manifest + Phase 3 stub without ffmpeg or a real video."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _make_frame(output_path: Path, variant: str = "blank") -> None:
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    if variant == "button_hover":
        draw.rectangle([860, 490, 1060, 550], fill=(70, 130, 180))
        draw.text((880, 510), "Click me", fill=(255, 255, 255))
    elif variant == "modal":
        draw.rectangle([560, 290, 1360, 790], fill=(255, 255, 255))
        draw.text((580, 310), "Modal dialog", fill=(0, 0, 0))
    elif variant == "toast":
        draw.rectangle([1620, 980, 1900, 1060], fill=(50, 200, 50))
        draw.text((1630, 995), "Saved!", fill=(255, 255, 255))
    elif variant == "typed":
        draw.rectangle([400, 400, 900, 450], fill=(255, 255, 255))
        draw.text((410, 415), "hello world", fill=(0, 0, 0))

    img.save(output_path, "PNG")


def _create_synthetic_frames(frames_dir: Path) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        (1, "blank"),         # base — always kept
        (2, "blank"),         # identical → DROPPED
        (3, "blank"),         # identical → DROPPED
        (4, "button_hover"),  # hover → KEPT
        (5, "button_hover"),  # identical → DROPPED
        (6, "modal"),         # modal → KEPT
        (7, "toast"),         # small toast → KEPT (region MAD)
        (8, "toast"),         # identical → DROPPED
        (9, "typed"),         # input filled → KEPT
    ]

    paths = []
    for num, variant in specs:
        p = frames_dir / f"frame_{num:06d}.png"
        _make_frame(p, variant)
        paths.append(p)
    return paths


def main() -> int:
    workdir = Path("output_smoke")
    if workdir.exists():
        shutil.rmtree(workdir)

    print("=== Smoke test — Phase 2 + Phase 3 ===\n")

    frame_paths = _create_synthetic_frames(workdir / "frames")
    print(f"Generated {len(frame_paths)} synthetic frames")

    from phases.phase2_extract import deduplicate, build_manifest

    kept = deduplicate(frame_paths, phash_threshold=8, mad_threshold=0.003)
    dropped = len(frame_paths) - len(kept)
    print(f"Kept:    {len(kept)} frames")
    print(f"Dropped: {dropped} frames")

    toast_path = str(workdir / "frames" / "frame_000007.png")
    toast_kept = toast_path in {str(p) for p, _ in kept}
    print(f"Toast frame kept: {'YES' if toast_kept else 'NO — region MAD threshold may be too high'}")

    manifest = build_manifest(kept, video_path=Path("synthetic.mp4"), fps=2)
    manifest_path = workdir / "manifest.json"
    manifest.save(manifest_path)
    print(f"Manifest written: {manifest_path} ({len(manifest.frames)} entries)\n")

    from phases.phase3_analyze import run as phase3_run
    import httpx as _httpx
    try:
        steps_path = phase3_run(manifest_path=manifest_path, output_dir=workdir)
        steps = json.loads(steps_path.read_text())
        print(f"steps.json written: {steps_path} ({len(steps)} actions)\n")
    except _httpx.ConnectError:
        print("Phase 3: Ollama not running — skipped (expected in smoke test)\n")
        steps_path = workdir / "steps.json"
        steps_path.write_text("[]", encoding="utf-8")

    ok = len(kept) < len(frame_paths) and manifest_path.exists() and steps_path.exists() and toast_kept
    print("=== RESULT:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

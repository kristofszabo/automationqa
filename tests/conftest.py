"""Shared fixtures for all phase tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw


def make_frame(path: Path, variant: str = "blank") -> None:
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

    img.save(path, "PNG")


@pytest.fixture()
def frames_dir(tmp_path: Path) -> Path:
    d = tmp_path / "frames"
    d.mkdir()
    return d

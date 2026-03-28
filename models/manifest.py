from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class FrameEntry:
    index: int
    path: str
    timestamp_ms: int
    diff_score: float | None = None


@dataclass
class Manifest:
    video: str
    fps_extracted: int
    frames: list[FrameEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Manifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        frames = [FrameEntry(**f) for f in data["frames"]]
        return cls(
            video=data["video"],
            fps_extracted=data["fps_extracted"],
            frames=frames,
        )

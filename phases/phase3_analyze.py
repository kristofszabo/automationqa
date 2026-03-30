from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from models.manifest import FrameEntry, Manifest

# ---------------------------------------------------------------------------
# Gemini config
# ---------------------------------------------------------------------------
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Available models (set GEMINI_MODEL env var to switch):
#   gemini-2.5-flash-lite    — free tier, legolcsobb (default)
#   gemini-2.5-flash         — free tier, jobb minőség
#   gemini-2.0-flash         — stable, paid
#   gemini-3-flash-preview   — latest preview
BATCH_SIZE = 10

# ---------------------------------------------------------------------------
# Action schema (produced into steps.json)
# ---------------------------------------------------------------------------
# Each step looks like:
# {
#   "step": 1,
#   "action": "navigate" | "click" | "type" | "assert",
#   "timestamp_ms": 0,
#   ... action-specific fields ...
# }

StepList = list[dict[str, Any]]

SYSTEM_PROMPT = """\
You are a UI action extractor. You receive a sequence of numbered screenshots \
from a screen recording. Analyse them and return ONLY a JSON array of actions \
that happened between the frames. Use this schema for each action:

navigate : { "action": "navigate", "url": "<url>", "timestamp_ms": <int> }
click    : { "action": "click", "selector": "<css or text>", "timestamp_ms": <int> }
type     : { "action": "type", "selector": "<css or text>", "value": "<text>", "timestamp_ms": <int> }
assert   : { "action": "assert", "selector": "<css or text>", "expected": "<text>", "timestamp_ms": <int> }

Rules:
- Output ONLY the JSON array, no explanation, no markdown code block.
- If nothing changed between frames, return [].
- Use the timestamp_ms values provided in the frame labels.
"""


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def _call_gemini(batch_frames: list[FrameEntry]) -> str:
    """Send a batch of frames to Gemini 1.5 Flash and return raw response text."""
    labels = "\n".join(
        f"Frame {i + 1} - timestamp_ms={f.timestamp_ms}"
        for i, f in enumerate(batch_frames)
    )
    parts: list[Any] = [f"Frames in this batch:\n{labels}\n\nExtract all UI actions."]
    for f in batch_frames:
        parts.append(types.Part.from_bytes(data=Path(f.path).read_bytes(), mime_type="image/png"))

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Strip markdown code fences if the model wrapped its output."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    return match.group(1).strip() if match else raw.strip()


def _parse_response(raw: str, batch_start_index: int, frames: list[FrameEntry]) -> StepList:
    """Parse raw LLM response into a list of action dicts."""
    try:
        actions = json.loads(_extract_json(raw))
        if not isinstance(actions, list):
            raise ValueError("Expected a JSON array")
        return actions
    except (json.JSONDecodeError, ValueError):
        print(f"[Phase 3] Warning: could not parse response for batch starting at {batch_start_index}")
        return []


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

def _frame_batches(manifest: Manifest, size: int):
    frames = manifest.frames
    for i in range(0, len(frames), size):
        yield i, frames[i:i + size]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(manifest_path: Path, output_dir: Path) -> Path:
    print(f"[Phase 3] Loading manifest from {manifest_path}…")
    manifest = Manifest.load(manifest_path)
    print(f"[Phase 3] Analysing {len(manifest.frames)} frames in batches of {BATCH_SIZE}…")

    all_actions: StepList = []

    for batch_start, batch_frames in _frame_batches(manifest, BATCH_SIZE):
        raw = _call_gemini(batch_frames)
        actions = _parse_response(raw, batch_start, batch_frames)
        all_actions.extend(actions)

    # Re-number steps sequentially
    for i, action in enumerate(all_actions, start=1):
        action["step"] = i

    steps_path = output_dir / "steps.json"
    steps_path.write_text(json.dumps(all_actions, indent=2), encoding="utf-8")
    print(f"[Phase 3] {len(all_actions)} actions written -> {steps_path}")
    return steps_path

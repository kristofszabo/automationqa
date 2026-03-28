from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx

from models.manifest import FrameEntry, Manifest

# ---------------------------------------------------------------------------
# Ollama / model config
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5vl"  # adjust to exact tag pulled in Phase 1
BATCH_SIZE = 10
REQUEST_TIMEOUT = 120  # seconds — vision inference is slow

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

def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _call_ollama(batch_frames: list[FrameEntry]) -> str:
    """Send a batch of frames to Qwen2.5-VL via Ollama and return raw response text.

    Retries once with half the batch on OOM (HTTP 500 containing 'out of memory').
    TODO: mask sensitive data (passwords, tokens) before sending images
    """
    images = [_encode_image(Path(f.path)) for f in batch_frames]
    labels = "\n".join(
        f"Frame {i + 1} — timestamp_ms={f.timestamp_ms}"
        for i, f in enumerate(batch_frames)
    )
    user_content = f"Frames in this batch:\n{labels}\n\nExtract all UI actions."

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content, "images": images},
        ],
        "stream": False,
    }

    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    except httpx.HTTPStatusError as e:
        body = e.response.text.lower()
        if e.response.status_code == 500 and "out of memory" in body and len(batch_frames) > 1:
            # OOM: retry with first half only
            mid = len(batch_frames) // 2
            print(f"[Phase 3] OOM on batch of {len(batch_frames)}, retrying with {mid} frames…")
            return _call_ollama(batch_frames[:mid])
        raise


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
        raw = _call_ollama(batch_frames)
        actions = _parse_response(raw, batch_start, batch_frames)
        all_actions.extend(actions)

    # Re-number steps sequentially
    for i, action in enumerate(all_actions, start=1):
        action["step"] = i

    steps_path = output_dir / "steps.json"
    steps_path.write_text(json.dumps(all_actions, indent=2), encoding="utf-8")
    print(f"[Phase 3] {len(all_actions)} actions written → {steps_path}")
    return steps_path

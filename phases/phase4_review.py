from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.serving import make_server

StepList = list[dict[str, Any]]

_REQUIRED: dict[str, list[str]] = {
    "navigate": ["url"],
    "click":    ["selector"],
    "type":     ["selector", "value"],
    "assert":   ["selector", "expected"],
}
_VALID_ACTIONS = set(_REQUIRED)


def _validate(steps: Any) -> list[str]:
    if not isinstance(steps, list):
        return ["Root must be a JSON array."]
    errors: list[str] = []
    for i, step in enumerate(steps):
        label = f"Step {i + 1}"
        if not isinstance(step, dict):
            errors.append(f"{label}: must be an object.")
            continue
        action = step.get("action")
        if action not in _VALID_ACTIONS:
            errors.append(
                f"{label}: invalid action '{action}' "
                f"(must be one of {sorted(_VALID_ACTIONS)})."
            )
            continue
        if not isinstance(step.get("timestamp_ms"), int):
            errors.append(f"{label}: 'timestamp_ms' must be an integer.")
        for field in _REQUIRED[action]:
            if not step.get(field):
                errors.append(
                    f"{label} ({action}): missing required field '{field}'."
                )
    return errors


def _create_app(steps_path: Path, done: threading.Event) -> Flask:
    dist_dir = Path(__file__).parent.parent / "web" / "dist"
    app = Flask(__name__, static_folder=str(dist_dir), static_url_path="")

    @app.get("/api/steps")
    def get_steps():
        data = json.loads(steps_path.read_text(encoding="utf-8"))
        return jsonify(data)

    @app.post("/api/validate")
    def validate():
        steps = request.get_json(force=True)
        return jsonify({"errors": _validate(steps)})

    @app.post("/api/save")
    def save():
        steps = request.get_json(force=True)
        errors = _validate(steps)
        if errors:
            return jsonify({"errors": errors}), 422
        for i, step in enumerate(steps, start=1):
            step["step"] = i
        steps_path.write_text(json.dumps(steps, indent=2), encoding="utf-8")
        print(f"[Phase 4] {len(steps)} steps saved -> {steps_path}")
        done.set()
        return jsonify({"ok": True})

    @app.get("/")
    @app.get("/<path:path>")
    def serve(path: str = ""):
        if path and (dist_dir / path).exists():
            return send_from_directory(dist_dir, path)
        return send_from_directory(dist_dir, "index.html")

    return app


def run(steps_path: Path, output_dir: Path) -> Path:
    done = threading.Event()
    app = _create_app(steps_path, done)

    server = make_server("localhost", 5000, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("[Phase 4] Review UI -> http://localhost:5000")
    threading.Timer(0.8, lambda: webbrowser.open("http://localhost:5000")).start()

    done.wait()
    server.shutdown()
    return steps_path

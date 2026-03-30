"""Tests for Phase 4 — schema validation and Flask API endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from phases.phase4_review import _validate


class TestValidate:
    def test_valid_click(self) -> None:
        steps = [{"action": "click", "selector": "button", "timestamp_ms": 100}]
        assert _validate(steps) == []

    def test_valid_navigate(self) -> None:
        steps = [{"action": "navigate", "url": "https://example.com", "timestamp_ms": 0}]
        assert _validate(steps) == []

    def test_valid_type(self) -> None:
        steps = [{"action": "type", "selector": "input", "value": "hello", "timestamp_ms": 200}]
        assert _validate(steps) == []

    def test_valid_assert(self) -> None:
        steps = [{"action": "assert", "selector": "h1", "expected": "Title", "timestamp_ms": 300}]
        assert _validate(steps) == []

    def test_empty_list_is_valid(self) -> None:
        assert _validate([]) == []

    def test_not_a_list(self) -> None:
        errors = _validate({"action": "click"})
        assert len(errors) == 1
        assert "array" in errors[0].lower()

    def test_invalid_action(self) -> None:
        steps = [{"action": "hover", "selector": "div", "timestamp_ms": 0}]
        errors = _validate(steps)
        assert any("hover" in e for e in errors)

    def test_missing_required_field(self) -> None:
        steps = [{"action": "click", "timestamp_ms": 0}]  # missing selector
        errors = _validate(steps)
        assert any("selector" in e for e in errors)

    def test_missing_url_for_navigate(self) -> None:
        steps = [{"action": "navigate", "timestamp_ms": 0}]
        errors = _validate(steps)
        assert any("url" in e for e in errors)

    def test_missing_value_for_type(self) -> None:
        steps = [{"action": "type", "selector": "input", "timestamp_ms": 0}]
        errors = _validate(steps)
        assert any("value" in e for e in errors)

    def test_timestamp_ms_not_int(self) -> None:
        steps = [{"action": "click", "selector": "btn", "timestamp_ms": "abc"}]
        errors = _validate(steps)
        assert any("timestamp_ms" in e for e in errors)

    def test_multiple_steps_multiple_errors(self) -> None:
        steps = [
            {"action": "click", "selector": "btn", "timestamp_ms": 0},  # valid
            {"action": "hover", "timestamp_ms": 0},                      # invalid action
            {"action": "type", "selector": "input", "timestamp_ms": 0}, # missing value
        ]
        errors = _validate(steps)
        assert len(errors) >= 2


class TestFlaskApi:
    @pytest.fixture()
    def client(self, tmp_path: Path):
        """Flask test client using the real _create_app from phase4_review."""
        import threading
        from phases.phase4_review import _create_app

        steps_path = tmp_path / "steps.json"
        steps_path.write_text("[]", encoding="utf-8")

        done = threading.Event()
        app = _create_app(steps_path, done)
        app.config["TESTING"] = True

        with app.test_client() as c:
            c._steps_path = steps_path  # type: ignore[attr-defined]
            yield c

    def test_get_steps_returns_list(self, client) -> None:
        res = client.get("/api/steps")
        assert res.status_code == 200
        assert isinstance(res.get_json(), list)

    def test_validate_valid_returns_no_errors(self, client) -> None:
        payload = [{"action": "click", "selector": "btn", "timestamp_ms": 0}]
        res = client.post("/api/validate", json=payload)
        assert res.status_code == 200
        assert res.get_json()["errors"] == []

    def test_validate_invalid_returns_errors(self, client) -> None:
        payload = [{"action": "hover", "timestamp_ms": 0}]
        res = client.post("/api/validate", json=payload)
        assert res.status_code == 200
        assert len(res.get_json()["errors"]) > 0

    def test_save_valid_writes_file(self, client) -> None:
        original = client._steps_path.read_text(encoding="utf-8")
        payload = [{"action": "click", "selector": "btn", "timestamp_ms": 0}]
        res = client.post("/api/save", json=payload)
        assert res.status_code == 200
        saved_text = client._steps_path.read_text(encoding="utf-8")
        assert saved_text != original
        saved = json.loads(saved_text)
        assert len(saved) == 1
        assert saved[0]["step"] == 1

    def test_save_invalid_returns_422(self, client) -> None:
        payload = [{"action": "unknown", "timestamp_ms": 0}]
        res = client.post("/api/save", json=payload)
        assert res.status_code == 422

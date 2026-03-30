"""Tests for Phase 3 — response parsing (no Gemini API calls)."""
from __future__ import annotations

from phases.phase3_analyze import _extract_json, _parse_response


class TestExtractJson:
    def test_plain_json_returned_as_is(self) -> None:
        raw = '[{"action": "click"}]'
        assert _extract_json(raw) == raw

    def test_strips_json_code_fence(self) -> None:
        raw = '```json\n[{"action": "click"}]\n```'
        assert _extract_json(raw) == '[{"action": "click"}]'

    def test_strips_plain_code_fence(self) -> None:
        raw = '```\n[{"action": "click"}]\n```'
        assert _extract_json(raw) == '[{"action": "click"}]'

    def test_strips_surrounding_whitespace(self) -> None:
        raw = '  [{"action": "click"}]  '
        assert _extract_json(raw) == '[{"action": "click"}]'


class TestParseResponse:
    def test_valid_array_returned(self) -> None:
        raw = '[{"action": "click", "selector": "button", "timestamp_ms": 100}]'
        result = _parse_response(raw, batch_start_index=0, frames=[])
        assert len(result) == 1
        assert result[0]["action"] == "click"

    def test_empty_array_returned(self) -> None:
        result = _parse_response("[]", batch_start_index=0, frames=[])
        assert result == []

    def test_invalid_json_returns_empty(self) -> None:
        result = _parse_response("not json at all", batch_start_index=0, frames=[])
        assert result == []

    def test_non_array_returns_empty(self) -> None:
        result = _parse_response('{"action": "click"}', batch_start_index=0, frames=[])
        assert result == []

    def test_fenced_json_parsed(self) -> None:
        raw = '```json\n[{"action": "navigate", "url": "https://example.com", "timestamp_ms": 0}]\n```'
        result = _parse_response(raw, batch_start_index=0, frames=[])
        assert len(result) == 1
        assert result[0]["action"] == "navigate"

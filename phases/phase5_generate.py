from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

_VALIDATION_DIR = Path(__file__).parent.parent / "validation"

SYSTEM_PROMPT = """\
You are a Playwright test generator. You receive a list of UI actions and optional DOM snapshots \
captured after each action. Generate a single Playwright TypeScript test file using @playwright/test.

Rules:
- Output ONLY the TypeScript code, no explanation, no markdown fences.
- Use a single test() block containing all steps in order.
- Prefer resilient selectors in this order:
    1. getByRole() with name
    2. getByLabel()
    3. getByText()
    4. locator('[data-testid="..."]')
    5. locator(css) — only as a last resort
- For assert steps use expect(page.locator(...)).toHaveText(...) or toBeVisible().
- Add a descriptive test name derived from the actions.
- Import only from @playwright/test.
"""

RETRY_PROMPT_SUFFIX = """

The previous attempt produced the following TypeScript compilation errors.
Fix all of them and return the corrected file:

{errors}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_code(raw: str) -> str:
    """Strip markdown code fences if the model wrapped its output."""
    match = re.search(r"```(?:typescript|ts)?\s*([\s\S]*?)```", raw)
    return match.group(1).strip() if match else raw.strip()


def _build_prompt(steps_with_snapshots: list[dict[str, Any]], tsc_errors: list[str] | None = None) -> str:
    lines: list[str] = ["UI actions to convert into a Playwright test:\n"]
    for s in steps_with_snapshots:
        step_num = s.get("step", "?")
        action = s.get("action", "")
        details = {k: v for k, v in s.items() if k not in ("step", "action", "snapshot_path", "snapshot")}
        lines.append(f"Step {step_num}: {action} {json.dumps(details)}")
        snapshot = s.get("snapshot", "")
        if snapshot:
            lines.append(f"  DOM after step (truncated):\n{snapshot[:3000]}\n")

    if tsc_errors:
        lines.append(RETRY_PROMPT_SUFFIX.format(errors="\n".join(tsc_errors)))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def _replay_and_snapshot(steps: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    """Replay steps in a headless browser and capture DOM snapshots after each action."""
    has_navigate = any(s.get("action") == "navigate" for s in steps)
    if not has_navigate:
        print("[Phase 5] Warning: no 'navigate' step found — skipping browser replay.")
        return [{**s, "snapshot": ""} for s in steps]

    snapshots_dir = output_dir / "snapshots"
    snapshots_dir.mkdir(exist_ok=True)

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    enriched: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        for step in steps:
            action = step.get("action")
            selector = step.get("selector", "")
            step_num = step.get("step", "?")

            try:
                if action == "navigate":
                    page.goto(step["url"], timeout=10_000)
                elif action == "click":
                    page.locator(selector).click(timeout=5_000)
                elif action == "type":
                    page.locator(selector).fill(step.get("value", ""), timeout=5_000)
                elif action == "assert":
                    pass  # just snapshot, no interaction
            except PWTimeout:
                print(f"[Phase 5] Warning: step {step_num} ({action}) timed out — continuing.")
            except Exception as exc:
                print(f"[Phase 5] Warning: step {step_num} ({action}) failed: {exc} — continuing.")

            html = page.content()
            snapshot_path = snapshots_dir / f"step_{step_num:02d}.html"
            snapshot_path.write_text(html, encoding="utf-8")
            enriched.append({**step, "snapshot": html, "snapshot_path": str(snapshot_path)})

        browser.close()

    return enriched


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def _call_gemini(steps_with_snapshots: list[dict[str, Any]], tsc_errors: list[str] | None = None) -> str:
    prompt = _build_prompt(steps_with_snapshots, tsc_errors)
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text


# ---------------------------------------------------------------------------
# TypeScript validation
# ---------------------------------------------------------------------------

def _validate_typescript(test_path: Path) -> list[str]:
    import shutil
    tmp = _VALIDATION_DIR / test_path.name
    shutil.copy2(test_path, tmp)
    try:
        result = subprocess.run(
            f'npx --prefix "{_VALIDATION_DIR}" tsc --noEmit'
            f' --project "{_VALIDATION_DIR / "tsconfig.json"}"',
            capture_output=True,
            text=True,
            shell=True,
        )
    finally:
        tmp.unlink(missing_ok=True)
    if result.returncode == 0:
        return []
    return [line for line in result.stdout.splitlines() + result.stderr.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(steps_path: Path, output_dir: Path) -> Path:
    print(f"[Phase 5] Loading steps from {steps_path}...")
    steps: list[dict[str, Any]] = json.loads(steps_path.read_text(encoding="utf-8"))

    print(f"[Phase 5] Replaying {len(steps)} steps in headless browser...")
    steps_with_snapshots = _replay_and_snapshot(steps, output_dir)

    print("[Phase 5] Generating Playwright TypeScript test...")
    raw = _call_gemini(steps_with_snapshots)
    test_code = _extract_code(raw)

    test_path = output_dir / "test_generated.spec.ts"
    test_path.write_text(test_code, encoding="utf-8")

    print("[Phase 5] Validating TypeScript compilation...")
    errors = _validate_typescript(test_path)

    if errors:
        print(f"[Phase 5] tsc reported {len(errors)} error(s), retrying with feedback...")
        raw2 = _call_gemini(steps_with_snapshots, tsc_errors=errors)
        test_path.write_text(_extract_code(raw2), encoding="utf-8")
        errors2 = _validate_typescript(test_path)
        if errors2:
            print(f"[Phase 5] Warning: {len(errors2)} tsc error(s) remain after retry — proceeding anyway.")
        else:
            print("[Phase 5] tsc validation passed after retry.")
    else:
        print("[Phase 5] tsc validation passed.")

    print(f"[Phase 5] Test written -> {test_path}")
    return test_path

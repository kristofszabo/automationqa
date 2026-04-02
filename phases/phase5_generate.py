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
You are a Playwright test generator. You receive a list of UI actions. \
Generate a single Playwright TypeScript test file using @playwright/test.

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
    match = re.search(r"```(?:typescript|ts)?\s*([\s\S]*?)```", raw)
    return match.group(1).strip() if match else raw.strip()


def _build_prompt(steps: list[dict[str, Any]], tsc_errors: list[str] | None = None) -> str:
    lines: list[str] = ["UI actions to convert into a Playwright test:\n"]
    for s in steps:
        step_num = s.get("step", "?")
        action = s.get("action", "")
        details = {k: v for k, v in s.items() if k not in ("step", "action")}
        lines.append(f"Step {step_num}: {action} {json.dumps(details)}")

    if tsc_errors:
        lines.append(RETRY_PROMPT_SUFFIX.format(errors="\n".join(tsc_errors)))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def _call_gemini(steps: list[dict[str, Any]], tsc_errors: list[str] | None = None) -> str:
    prompt = _build_prompt(steps, tsc_errors)
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

    print(f"[Phase 5] Generating Playwright TypeScript test from {len(steps)} steps...")
    raw = _call_gemini(steps)
    test_code = _extract_code(raw)

    test_path = output_dir / "test_generated.spec.ts"
    test_path.write_text(test_code, encoding="utf-8")

    print("[Phase 5] Validating TypeScript compilation...")
    errors = _validate_typescript(test_path)

    if errors:
        print(f"[Phase 5] tsc reported {len(errors)} error(s), retrying with feedback...")
        raw2 = _call_gemini(steps, tsc_errors=errors)
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

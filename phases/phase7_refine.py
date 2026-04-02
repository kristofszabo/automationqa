from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

_VALIDATION_DIR = Path(__file__).parent.parent / "validation"

SYSTEM_PROMPT = """\
You are a Playwright test generator. You receive:
- The current generated test code
- The result of running that test (pass/fail + output)
- DOM snapshots captured via step replay

Improve and finalize the Playwright TypeScript test based on this real execution data.

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
- Fix any selector or assertion errors revealed by the test run.
- Import only from @playwright/test.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_code(raw: str) -> str:
    match = re.search(r"```(?:typescript|ts)?\s*([\s\S]*?)```", raw)
    return match.group(1).strip() if match else raw.strip()


def _build_prompt(
    test_code: str,
    passed: bool,
    steps: list[dict[str, Any]],
) -> str:
    status = "PASSED" if passed else "FAILED"
    failed_steps = [s for s in steps if not s.get("success")]
    lines = [
        f"Current test code:\n```typescript\n{test_code}\n```\n",
        f"Step replay result: {status}",
    ]
    if failed_steps:
        lines.append("Failed steps:")
        for s in failed_steps:
            lines.append(f"  Step {s['step']} ({s['action']}): {s.get('error', 'unknown error')}")
    lines.append("\nDOM snapshots captured during step replay:")

    for s in steps:
        step_num = s.get("step", "?")
        action = s.get("action", "")
        details = {k: v for k, v in s.items() if k not in ("step", "action", "snapshot_path")}
        lines.append(f"\nStep {step_num}: {action} {json.dumps(details)}")
        snapshot_path = s.get("snapshot_path", "")
        if snapshot_path:
            try:
                snapshot = Path(snapshot_path).read_text(encoding="utf-8")
                lines.append(f"DOM after step (truncated):\n{snapshot[:3000]}")
            except OSError:
                pass
    return "\n".join(lines)


def _call_gemini(prompt: str) -> str:
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text


def _validate_typescript(test_path: Path) -> list[str]:
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

def run(run_results_path: Path, test_path: Path, output_dir: Path) -> Path:
    print(f"[Phase 7] Loading run results from {run_results_path}...")
    run_results: dict[str, Any] = json.loads(run_results_path.read_text(encoding="utf-8"))

    passed: bool = run_results["passed"]
    steps: list[dict[str, Any]] = run_results["steps"]

    print("[Phase 7] Generating refined test via Gemini...")
    test_code = test_path.read_text(encoding="utf-8")
    prompt = _build_prompt(test_code, passed, steps)
    raw = _call_gemini(prompt)
    final_code = _extract_code(raw)

    final_path = output_dir / "test_final.spec.ts"
    final_path.write_text(final_code, encoding="utf-8")

    print("[Phase 7] Validating TypeScript compilation...")
    errors = _validate_typescript(final_path)

    if errors:
        print(f"[Phase 7] tsc reported {len(errors)} error(s), retrying with feedback...")
        retry_prompt = prompt + "\n\nTypeScript compilation errors to fix:\n" + "\n".join(errors)
        raw2 = _call_gemini(retry_prompt)
        final_path.write_text(_extract_code(raw2), encoding="utf-8")
        errors2 = _validate_typescript(final_path)
        if errors2:
            print(f"[Phase 7] Warning: {len(errors2)} tsc error(s) remain after retry — proceeding anyway.")
        else:
            print("[Phase 7] tsc validation passed after retry.")
    else:
        print("[Phase 7] tsc validation passed.")

    print(f"[Phase 7] Final test written -> {final_path}")
    return final_path

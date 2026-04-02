from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(workdir: Path) -> dict[str, Any]:
    """Load optional config.json from workdir. Returns empty dict if missing."""
    config_path = workdir / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Replay + DOM snapshot
# ---------------------------------------------------------------------------

def _replay_and_snapshot(
    steps: list[dict[str, Any]],
    output_dir: Path,
    headless: bool = True,
    video: bool = False,
    trace: bool = False,
    base_url: str | None = None,
    storage_state: Path | None = None,
) -> list[dict[str, Any]]:
    has_navigate = any(s.get("action") == "navigate" for s in steps)
    if not has_navigate and not base_url:
        print("[Phase 6] Warning: no 'navigate' step and no base_url — skipping browser replay.")
        return [{**s, "snapshot_path": "", "success": False, "error": "no navigation"} for s in steps]

    snapshots_dir = output_dir / "snapshots_phase6"
    snapshots_dir.mkdir(exist_ok=True)

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    enriched: list[dict[str, Any]] = []
    video_dir = output_dir / "videos_phase6" if video else None
    if video_dir:
        video_dir.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)

        context_kwargs: dict[str, Any] = {}
        if video_dir:
            context_kwargs["record_video_dir"] = str(video_dir)
        if base_url:
            context_kwargs["base_url"] = base_url

        context = browser.new_context(**context_kwargs)

        # Apply cookies before navigation (no temp page needed)
        if storage_state and storage_state.exists():
            state = json.loads(storage_state.read_text(encoding="utf-8"))
            if state.get("cookies"):
                context.add_cookies(state["cookies"])

        page = context.new_page()

        if trace:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        if not has_navigate and base_url:
            print(f"[Phase 6] No 'navigate' step found — using base_url: {base_url}")
            page.goto(base_url, timeout=10_000)

        # Apply localStorage — must navigate to the origin first to avoid SecurityError on about:blank
        if storage_state and storage_state.exists():
            state = json.loads(storage_state.read_text(encoding="utf-8"))
            for origin_data in state.get("origins", []):
                ls_entries = origin_data.get("localStorage", [])
                if not ls_entries:
                    continue
                origin_url = origin_data.get("origin", "")
                if origin_url:
                    page.goto(origin_url, timeout=10_000)
                for entry in ls_entries:
                    page.evaluate(
                        "([k, v]) => window.localStorage.setItem(k, v)",
                        [entry["name"], entry["value"]],
                    )

        for step in steps:
            action = step.get("action")
            raw_selector = step.get("selector", "")
            step_num = step.get("step", "?")

            # Convert jQuery :contains() to Playwright text= selector
            selector = re.sub(
                r":contains\(['\"](.+?)['\"]\)",
                lambda m: f" >> text={m.group(1)}",
                raw_selector,
            ).strip()
            success = True
            error: str | None = None

            try:
                if action == "navigate":
                    page.goto(step["url"], timeout=10_000)
                elif action == "click":
                    page.locator(selector).click(timeout=5_000)
                elif action == "type":
                    page.locator(selector).fill(step.get("value", ""), timeout=5_000)
                elif action == "assert":
                    pass
            except PWTimeout as exc:
                success = False
                error = f"Timeout: {exc}"
                print(f"[Phase 6] Warning: step {step_num} ({action}) timed out — continuing.")
            except Exception as exc:
                success = False
                error = str(exc)
                print(f"[Phase 6] Warning: step {step_num} ({action}) failed: {exc} — continuing.")

            html = page.content()
            snapshot_path = snapshots_dir / f"step_{step_num:02d}.html"
            snapshot_path.write_text(html, encoding="utf-8")
            enriched.append({**step, "snapshot_path": str(snapshot_path), "success": success, "error": error})

        video_path: str | None = None
        if video:
            video_path = page.video.path() if page.video else None

        if trace:
            trace_path = output_dir / "trace_phase6.zip"
            context.tracing.stop(path=str(trace_path))
            print(f"[Phase 6] Trace saved -> {trace_path}")
            print("[Phase 6] View trace: npx playwright show-trace " + str(trace_path))

        context.close()
        browser.close()

        if video and video_path:
            print(f"[Phase 6] Video saved -> {video_path}")

    return enriched


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(
    steps_path: Path,
    output_dir: Path,
    headless: bool = True,
    video: bool = False,
    trace: bool = False,
    base_url: str | None = None,
    storage_state: Path | None = None,
) -> Path:
    if base_url:
        print(f"[Phase 6] Base URL: {base_url}")
    if storage_state:
        print(f"[Phase 6] Storage state: {storage_state}")

    mode = "headed" if not headless else "headless"
    extras = ", ".join(f for f, on in [("video", video), ("trace", trace)] if on)
    extras_note = f" + {extras}" if extras else ""
    print(f"[Phase 6] Replaying steps and capturing DOM snapshots ({mode}{extras_note})...")

    steps: list[dict[str, Any]] = json.loads(steps_path.read_text(encoding="utf-8"))
    enriched_steps = _replay_and_snapshot(
        steps, output_dir,
        headless=headless, video=video, trace=trace,
        base_url=base_url, storage_state=storage_state,
    )

    passed = all(s.get("success", False) for s in enriched_steps)
    failed = [s for s in enriched_steps if not s.get("success")]
    if failed:
        print(f"[Phase 6] {len(failed)} step(s) failed:")
        for s in failed:
            print(f"  Step {s['step']} ({s['action']}): {s['error']}")
    else:
        print("[Phase 6] All steps completed successfully.")

    results_path = output_dir / "run_results.json"
    results_path.write_text(
        json.dumps({
            "passed": passed,
            "steps": enriched_steps,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[Phase 6] Results saved -> {results_path}")
    return results_path

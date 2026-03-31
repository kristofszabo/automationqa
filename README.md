# automationqa

Converts a screen recording into a Playwright test by extracting frames, analysing UI actions with Gemini Vision, and letting you review and correct the steps before code generation.

## Requirements

- Python 3.11+
- Node 18+ (for the review UI and TypeScript validation)
- ffmpeg (must be on PATH)
- A Gemini API key

```bash
pip install -r requirements.txt
playwright install chromium
cd web && npm install && npm run build
cd ../validation && npm install
```

Set your API key:

```bash
export GEMINI_API_KEY=your_key_here
```

---

## Phases

### Phase 2 — Frame Extraction

Extracts frames from a screen recording at a given fps, then deduplicates them using perceptual hashing (pHash) and region MAD to drop frames that are visually identical.

**Output:** `<workdir>/frames/frame_*.png`, `<workdir>/manifest.json`

```bash
npm run phase2 -- --video path/to/recording.mp4
npm run phase2 -- --video path/to/recording.mp4 --workdir output --fps 2
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--video` | — | Path to the screen recording (required) |
| `--workdir` | `output` | Directory for all artifacts |
| `--fps` | `2` | Frames per second to extract |
| `--phash-threshold` | `8` | pHash hamming distance below which frames are dropped |
| `--mad-threshold` | `0.003` | Region MAD max below which frames are dropped |

---

### Phase 3 — Vision Analysis

Sends the extracted frames to Gemini Vision in batches and extracts a list of UI actions (navigate, click, type, assert).

**Input:** `<workdir>/manifest.json`
**Output:** `<workdir>/steps.json`

```bash
npm run phase3
npm run phase3 -- --workdir output
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--workdir` | `output` | Directory containing `manifest.json` |

You can switch the Gemini model via the `GEMINI_MODEL` environment variable:

```bash
GEMINI_MODEL=gemini-2.5-flash npm run phase3
```

---

### Phase 4 — Step Review

Opens a browser-based UI where you can correct, add, or remove steps before the test is generated. The server validates the schema on every change and only allows saving when all steps are valid.

**Input:** `<workdir>/steps.json`
**Output:** updated `steps.json`

```bash
npm run phase4
npm run phase4 -- --steps output/steps.json
npm run phase4 -- --workdir output
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--steps` | `<workdir>/steps.json` | Path to steps.json |
| `--workdir` | `output` | Used to resolve the default steps path |

---

### Phase 5 — Test Generation

Replays the validated steps in a headless Chromium browser to collect a live DOM snapshot after each action. Feeds the steps and snapshots to Gemini to generate a Playwright TypeScript test using resilient selectors. Validates the output compiles with `tsc --noEmit` before proceeding (retries once with compiler errors as feedback if needed).

**Input:** `<workdir>/steps.json`
**Output:** `<workdir>/test_generated.spec.ts`, `<workdir>/snapshots/step_*.html`

```bash
npm run phase5
npm run phase5 -- --workdir output
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--workdir` | `output` | Directory containing `steps.json` |

> Note: Browser replay requires a `navigate` step as the first action. Without it, snapshots are skipped and the test is generated from steps alone.

---

## Running the full pipeline

```bash
python main.py --video path/to/recording.mp4
```

This runs Phase 2 → Phase 3 → Phase 4 → Phase 5 in sequence.

---

## Tests

```bash
npm test                # all tests
npm run test:phase2     # Phase 2 only
npm run test:phase3     # Phase 3 only
npm run test:phase4     # Phase 4 only
```

---

## Step schema

Each entry in `steps.json` follows one of these shapes:

```json
{ "step": 1, "action": "navigate", "url": "https://example.com", "timestamp_ms": 0 }
{ "step": 2, "action": "click",    "selector": "button#submit",   "timestamp_ms": 500 }
{ "step": 3, "action": "type",     "selector": "input#name",      "value": "Alice", "timestamp_ms": 1000 }
{ "step": 4, "action": "assert",   "selector": "h1",              "expected": "Welcome", "timestamp_ms": 1500 }
```

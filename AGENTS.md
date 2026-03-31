# AGENTS.md — automationqa

This file describes the project structure and context for AI agents (e.g. Claude Code) to navigate and work in this codebase effectively.

---

## What is this project?

**automationqa** is an end-to-end automated test generation tool that converts screen recordings (MP4 videos) into Playwright TypeScript tests.

Pipeline overview:
1. **Frame extraction** — extracts and deduplicates frames from a video
2. **Vision analysis** — Google Gemini Vision AI identifies UI interactions
3. **Manual review** — steps can be corrected via a web editor UI
4. **Test generation** — generates TypeScript Playwright test code and validates it by compiling with TypeScript

---

## File structure

```
automationqa/
├── main.py                      # Full pipeline orchestrator
├── requirements.txt             # Python dependencies
├── package.json                 # npm scripts for running phases & tests
│
├── phases/
│   ├── phase2_extract.py        # Phase 2: frame extraction via ffmpeg + deduplication
│   ├── phase3_analyze.py        # Phase 3: Gemini Vision API integration
│   ├── phase4_review.py         # Phase 4: Flask server for the review UI
│   └── phase5_generate.py       # Phase 5: test generation + TypeScript validation
│
├── start-scripts/
│   ├── phase2.py                # Standalone Phase 2 launcher
│   ├── phase3.py                # Standalone Phase 3 launcher
│   ├── review.py                # Standalone Phase 4 launcher
│   └── phase5.py                # Standalone Phase 5 launcher
│
├── models/
│   └── manifest.py              # Data models (manifest, frame metadata)
│
├── web/                         # Phase 4 React UI
│   ├── src/                     # React + TypeScript source
│   │   └── types.ts             # Step type definitions
│   └── dist/                    # Build output (served by Flask)
│
├── validation/                  # TypeScript compilation validation setup
│   ├── package.json             # @playwright/test + typescript dev-deps
│   └── tsconfig.json            # tsc config (strict, noEmit, *.spec.ts)
│
├── tests/                       # pytest test suite
│   ├── test_phase2.py
│   ├── test_phase3.py
│   └── test_phase4.py
└── test_smoke.py                # Standalone integration smoke test
```

---

## Phases in detail

### Phase 2 — Frame extraction (`phases/phase2_extract.py`)
- **Input**: MP4 video file
- **Output**: `<workdir>/frames/frame_*.png`, `<workdir>/manifest.json`
- Extracts frames via ffmpeg (default: 2 fps)
- Two-level deduplication:
  - **pHash** — perceptual hash with Hamming distance threshold (default: 8)
  - **MAD** — Region Mean Absolute Difference over a 3×3 grid (default: 0.003)
- Arguments: `--video`, `--workdir`, `--fps`, `--phash-threshold`, `--mad-threshold`

### Phase 3 — Vision analysis (`phases/phase3_analyze.py`)
- **Input**: `manifest.json`
- **Output**: `<workdir>/steps.json` — array of UI actions
- Sends frames to Google Gemini Vision API in batches (default: 10 frames/request)
- Extracted action types: `navigate`, `click`, `type`, `assert`
- Env vars: `GEMINI_API_KEY` (required), `GEMINI_MODEL` (default: `gemini-2.5-flash-lite`)
- Available models: `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-2.0-flash`

### Phase 4 — Step review (`phases/phase4_review.py`)
- **Input**: `steps.json`
- **Output**: updated `steps.json`
- Starts a Flask server on `localhost:5000`, serves the React UI from `web/dist`
- API endpoints:
  - `GET /api/steps` — fetch current steps
  - `POST /api/validate` — validate JSON against schema
  - `POST /api/save` — save steps (only succeeds if validation passes)
- Auto-opens the browser on startup
- Arguments: `--workdir`, `--steps`

### Phase 5 — Test generation (`phases/phase5_generate.py`)
- **Input**: `steps.json`
- **Output**: `<workdir>/test_generated.spec.ts`, `<workdir>/snapshots/step_*.html`
- **Browser replay**: replays steps in headless Playwright Chromium, captures HTML snapshot after each action
- **Code generation**: sends steps + snapshots to Gemini → TypeScript Playwright test
- Selector priority: `getByRole` > `getByLabel` > `getByText` > `data-testid` > CSS
- **Validation**: runs `tsc --noEmit` in the `validation/` directory
- **Retry logic**: if compilation fails, sends errors back to Gemini for one retry
- Arguments: `--workdir`

---

## Data schemas

### `manifest.json`
```json
{
  "video": "path/to/recording.mp4",
  "fps_extracted": 2,
  "frames": [
    { "index": 0, "path": "output/frames/frame_000001.png", "timestamp_ms": 0, "diff_score": null },
    { "index": 1, "path": "output/frames/frame_000024.png", "timestamp_ms": 11500, "diff_score": 0.012 }
  ]
}
```

### `steps.json`
```json
[
  { "step": 1, "action": "navigate", "url": "https://example.com", "timestamp_ms": 0 },
  { "step": 2, "action": "click", "selector": "button#submit", "timestamp_ms": 500 },
  { "step": 3, "action": "type", "selector": "input#name", "value": "Alice", "timestamp_ms": 1000 },
  { "step": 4, "action": "assert", "selector": "h1", "expected": "Welcome", "timestamp_ms": 1500 }
]
```

Required fields per step: `step` (number), `action` (navigate/click/type/assert), `timestamp_ms` (int), plus action-specific fields.

---

## Running the project

### Full pipeline
```bash
python main.py --video recording.mp4 [--workdir output] [--fps 2]
```

### Individual phases (npm scripts)
```bash
npm run phase2 -- --video recording.mp4 --workdir output
npm run phase3 -- --workdir output
npm run phase4 -- --workdir output
npm run phase5 -- --workdir output
```

### Tests
```bash
npm test                # all pytest tests
npm run test:phase2
npm run test:phase3
npm run test:phase4
python test_smoke.py    # smoke test (runs without ffmpeg or a real video)
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Gemini model to use (default: `gemini-2.5-flash-lite`) |

---

## System requirements

- Python 3.11+
- Node.js 18+
- ffmpeg (must be on PATH)
- Google Gemini API key

---

## Key architectural decisions

- **Filesystem-based**: no database; all state lives in JSON + PNG files
- **Stateless, idempotent phases**: any phase can be re-run independently
- **TypeScript validation**: the `validation/` directory exists solely to run `tsc --noEmit` on the generated `.spec.ts` file
- **No authentication**: single-user, local tool
- **Gemini Vision as AI engine**: previously used Ollama, replaced by the Gemini API

---
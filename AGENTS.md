# TTSkill

AI coaching for table tennis from the video on your phone, built for HackPrinceton Fall 2026.

- **Target user:** amateur players who want to learn from pros and review their own matches. They are on their phones, often courtside, uploading video they just filmed or pasting a YouTube link.
- **Tracks:** Entertainment, Amazon Practical AI, ChatOverflow, LangChain deepagents.

## Features

Every video input accepts an upload or a pasted YouTube link (watch, youtu.be or Shorts; up to 3 minutes; fetched at <=720p by `app/download.py` and deleted after the job).

**TT Coach** (`/coach`). One plain-language request plus a video. A LangChain deepagents agent with Claude:
- plans with `write_todos`; the todo list streams to the page live
- delegates to the subagents `clip_analyst`, `player_matcher` and `coach_writer`
- keeps its plan and notes in the virtual file system (`/plan.md`, `/pose_summary.json`, ...)
- calls six tools that wrap the pipelines below

Without `ANTHROPIC_API_KEY`, or if the agent fails, the same tools run on a fixed plan built from the request.

**Technique Breakdown** (`/breakdown`). A clip of a player the user admires, or a text description of their training, plus an optional stroke type: forehand topspin, forehand drive, forehand loop vs backspin, backhand topspin, backhand flick, backhand push, chop or serve. Blank means auto-detect from the swing or the text.
- The result is a vertical 1080x1920 coaching video in the measured style from `style/swift_style.json`:
  - a persistent header
  - 3 two-word cues, each in its own colour, with a slow-motion lead-in and a freeze frame
  - a bat-hand ring and trail in the cue's colour
  - a recap, then a practice drill
- Pipeline: pick a window → 720p proxy → MediaPipe pose → stroke type → key moments (the swing direction depends on the stroke type) → analyzer → `StrokeBreakdown` → render.
- The analyzer uses Claude vision (structured output) when `ANTHROPIC_API_KEY` is set, and the offline per-stroke templates otherwise. Text-only input renders cards only.

**Find my pro match** (`/match`). The user's swing, forehand or backhand, and an optional height; otherwise height is estimated from the table (76 cm high, 274 cm long).
- Only pros with the same bat hand are considered. A weighted distance on height and body proportions picks the top 3. DTW on the stroke's joint-angle curves says where the user's form differs from each.
- The result: 3 pros with scores and notes, plus one video of their cached breakdowns.
- Pro data lives in `backend/data/players/`: 12 players today, roadmap 100.

**Match Auto-Cut** (`/autocut`). The user's own match. Rallies are found from the sound of ball contact: 2–6 kHz band-pass → onset spikes over a rolling median → hits grouped into rallies by `gap` and `min_hits`.
- `highlights` mode keeps the top N rallies by hit count as separate clips.
- `full` mode keeps every rally, merges overlapping spans and drops the dead time.
- Each segment gets 1.5 s of padding, is re-encoded to 720p/30fps H.264, and the parts are joined with the ffmpeg concat demuxer.

## Stack and layout

```
Browser ──> Next.js /api/jobs/* ──> FastAPI /jobs/* ──> background pipeline ──> backend/data/jobs/<id>/
```

| Path | What |
| --- | --- |
| `frontend/` | Next.js 15 App Router, React 19, TypeScript (strict), Tailwind CSS v4. Deploys to Vercel with root directory `frontend`. |
| `frontend/app/` | Pages: `/`, `/coach`, `/breakdown`, `/match`, `/autocut`, `/jobs/[id]`. Shared UI lives in `ui.tsx`, `nav.tsx`, `video-picker.tsx`, `hero-video.tsx`. |
| `frontend/app/api/jobs/` | Route handlers. They validate the form, then call `lib/jobs.ts`. |
| `frontend/lib/jobs.ts` | Server-only job client with three modes: **proxy** to FastAPI when `BACKEND_URL` is set; **stub** (in-memory jobs with fake progress) when it is unset; **demo** (`DEMO_MODE=1`, every submission returns the cached results in `lib/demo-jobs.json` + `public/demo/*.mp4`). |
| `frontend/lib/submit.ts` | Client upload via XHR, which reports upload progress. Also holds the `Job` and `Breakdown` types. |
| `backend/app/main.py` | FastAPI endpoints. They validate input, save the upload, create the job and start a background task. |
| `backend/app/pipelines.py` | `run_autocut` and `run_breakdown`. Plain functions that update the job record as they go. |
| `backend/app/rally.py`, `cut.py` | Auto-Cut: hit and rally detection; padding, cutting and joining segments. |
| `backend/app/download.py` | Pasted YouTube links (watch, youtu.be, Shorts) via yt-dlp: probed before the job starts (private, unavailable, over 3 min fail on the form), downloaded at <=720p into the job folder, deleted after the pipeline runs. |
| `backend/app/jobs.py` | Job records as JSON at `backend/data/jobs/<id>/job.json`. Results go to `result.mp4` in the same folder. |
| `backend/technique/` | Breakdown pipeline (`pipeline.py`, `pose.py`, `analyze.py`, `render.py`, `schema.py`). Has its own CLI (`python -m technique`) and its own [README](backend/technique/README.md). |
| `backend/technique/strokes.py` | Stroke types (forehand topspin, drive, loop vs backspin, backhand topspin/flick/push, chop, serve): swing direction for key moments, coaching focus for the Claude prompt, and auto-detection from pose features or text. |
| `backend/style/` | Teaching-style profile. `fetch_refs.py` downloads reference videos into git-ignored `backend/data/style_ref/` (never commit or serve them), `analyze_refs.py` measures pacing, freeze frames, slow motion and text layout, `build_style.py` writes `swift_style.json`. `technique/style.py` loads it for the renderer (pacing, phase colours), the offline templates and the Claude prompt. |
| `backend/technique/fonts/` | Barlow and Barlow Condensed (SIL OFL, see `OFL.txt`) so videos match the app's type. |
| `backend/players/` | Find my pro match. `body.py` (limb ratios, stance width, joint-angle curves from a pose track), `table.py` (height from the table: 76 cm high, 274 cm long), `match.py` (same bat hand, weighted distance on height and proportions for the top 3, DTW on the stroke's angle curves for form differences), `compile.py` (one video of the matched pros' cached breakdowns), `build.py` (searches YouTube, cuts ~8 s clips at 720p, runs the pipeline, caches each breakdown, deletes raw downloads; resumable, `--local` adds a clip from a file). |
| `backend/data/players/` | `players.json` (12 pros: height, bat hand, clip references) and `profiles.json` (computed numbers) are committed; clips and rendered videos in the same folder are git-ignored. |
| `backend/agent/` | TT Coach. `coach.py` builds the deepagents agent (Claude, `write_todos` planning, virtual file system, subagents `clip_analyst`, `player_matcher`, `coach_writer`), streams its todos and files into the job, and falls back to a fixed plan without a key. `tools.py` holds the six tools, bound to one job, wrapping the existing pipelines. |
| `backend/technique/tools.py` | The same steps as plain functions (`TOOLS`), ready for a future deepagents orchestrator. |
| `samples/` | Local test videos. Git-ignored. |

### API

| Method | Path | Body |
| --- | --- | --- |
| POST | `/jobs/autocut` | multipart: `video` or `url` (YouTube link), `mode` (`highlights`/`full`), `top_n`, `threshold`, `gap`, `min_hits` |
| POST | `/jobs/breakdown` | multipart: `stroke_type` (optional, blank = auto-detect), `text` and/or `video` or `url`, `player`, `hand` (`auto`/`left`/`right`); legacy `stroke` still accepted |
| POST | `/jobs/coach` | multipart: `request`, `video` or `url` |
| GET | `/jobs/{id}/files/{name}` | Videos the coach made (`highlights.mp4`, `breakdown.mp4`, `pro_matches.mp4`) |
| POST | `/jobs/match` | multipart: `video` or `url`, `stroke` (`forehand`/`backhand`), `height_cm` (optional), `hand` |
| GET | `/jobs/{id}` | Job record |
| GET | `/jobs/{id}/result` | Result MP4 |
| GET | `/health` | `{"ok": true}` |

The frontend exposes the same paths under `/api/jobs/...`. FastAPI's interactive docs are at http://localhost:8000/docs.

The job record has these fields:
- Always: `id`, `kind`, `status` (`queued`/`running`/`done`/`failed`), `progress` (0–1), `message`, `params`, `resultUrl`.
- Auto-Cut adds `rallies`.
- Breakdown adds `breakdown`, `videoPrompt`, `analyzer`, `batHand` and `window`.

The job page polls `GET /jobs/{id}`.

## Install and run

Requirements:
- Node 20+, Python 3.11+ and ffmpeg/ffprobe on `PATH`.
- On Linux and WSL, MediaPipe also needs the OpenGL ES/EGL libraries. Without them, a breakdown fails with `OSError: libGLESv2.so.2`.

```bash
sudo apt install -y ffmpeg libegl1 libgles2   # Linux / WSL, one time

make install    # creates backend/.venv, pip installs, npm installs
make dev        # frontend on :3000, backend on :8000 (Ctrl-C stops both)
```

To run the services one at a time, use `make backend` or `make frontend`. To work on the UI without Python, run `cd frontend && npm run dev`; the API routes then run in stub mode.

Data builders (all run from `backend/`):
- `.venv/bin/python -m players.build` builds the pro profiles. It's resumable and stops when YouTube rate-limits; re-run it later. `--local PLAYER STROKE FILE URL TITLE` adds one clip from a file.
- `.venv/bin/python -m style.fetch_refs && .venv/bin/python -m style.analyze_refs && .venv/bin/python -m style.build_style` rebuilds the coaching-style profile.

Space YouTube requests out. Never work around its bot check by switching clients or using someone's cookies; wait and retry instead.

### Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `BACKEND_URL` | frontend | FastAPI URL. Unset means stub mode. `make frontend` sets it to `http://localhost:8000`. |
| `DEMO_MODE` | frontend | `1` makes every submission return the cached demo jobs. |
| `ANTHROPIC_API_KEY` | backend | Enables the Claude vision analyzer and the TT Coach deep agent. Without it, the offline analyzer and the coach's fixed plan run. |
| `COACH_MODEL` | backend | Claude model for TT Coach (default `claude-opus-5-5`). |
| `TECHNIQUE_MODEL` | backend | Claude model id for the analyzer (default `claude-opus-5-5`). |
| `POSE_MODEL_PATH` | backend | Local `pose_landmarker_full.task`. Otherwise it is downloaded once to `~/.cache/ttskill/`. |
| `TTSKILL_SAMPLE` | tests | Sample video for the technique end-to-end test. |

Frontend variables go in `frontend/.env.local`; see `frontend/.env.example`. Never commit secrets: `.env*.local` is git-ignored.

## Tests and checks

```bash
make test                                              # all backend tests (backend/tests + backend/technique/tests)
cd backend && .venv/bin/python -m pytest tests/test_cut.py -q   # a single file
cd frontend && npx tsc --noEmit                        # type check
cd frontend && npm run build                           # production build
```

- Tests that need a real match skip unless `samples/IMG_8782.MOV` exists, or `TTSKILL_SAMPLE` is set for the technique test.
- Render and cut tests need ffmpeg. Pose tests need `libegl1`/`libgles2`.
- Add a test with each backend change. Pure functions such as `padded_segments` and `group_rallies` should be tested without video files.

## Code conventions

General
- Keep changes small and in the style of the surrounding code. Don't add abstractions, dependencies or config that the change doesn't need.
- Write short comments that explain *why*, not what. Each module starts with a one-line docstring saying what it is for.

Backend (Python)
- Start every module with `from __future__ import annotations`. Type-hint function signatures; use `Path` for file paths.
- Call ffmpeg/ffprobe through `subprocess.run([...], check=True)` with a list of arguments, never a shell string.
- Pipelines are plain functions: `run_<kind>(job_id, ...)`.
  - Report progress with `jobs.update(job_id, status=..., progress=..., message=...)`.
  - Wrap the whole body in `try/except Exception`, print the traceback, and mark the job `failed` with a readable `message`. The job page shows it.
- Import heavy modules (MediaPipe, OpenCV) inside the pipeline function, so the API starts fast.
- Endpoints validate input and return `HTTPException(400, "...")` with a message a user can act on. The Next.js layer turns FastAPI's `{detail}` into `{error}`.
- `StrokeBreakdown` in `technique/schema.py` is the contract between analysis, prompting and rendering. If you change it, update the `Breakdown` type in `frontend/lib/submit.ts` to match.
- Hit detection exists in both `app/rally.py` and `technique/audio.py`. Keep the two in step.

Frontend (TypeScript)
- Use strict TypeScript and the `@/` import alias. Add `"use client"` only to components that need state or browser APIs.
- `lib/jobs.ts` is `server-only`. Client code talks only to `/api/jobs/*`, never to the backend directly.
- API routes validate the form first and return `{ error }` with a 400, then delegate to `createJob` / `getJob` / `getResult`.
- Pass the `range` header through on video results; iOS Safari needs it to seek.

Adding things
- **A new job kind:**
  - backend: an endpoint in `main.py` and `run_<kind>` in `pipelines.py`
  - frontend: a route at `frontend/app/api/jobs/<kind>/route.ts`, the kind added to the `Job["kind"]` union, a form page, and handling on `jobs/[id]/page.tsx`
  - a demo entry in `demo-jobs.json` if it should work in `DEMO_MODE`
- **A new stroke type:** add it to `STROKE_TYPES` in `backend/technique/strokes.py` (label, swing direction, phases, coaching focus), give it an offline template in `technique/analyze.py`, extend `classify()`/`from_text()` if it can be auto-detected, and add it to `frontend/lib/strokes.ts`.
- **A new pipeline step for agents:** expose it as a plain function in `technique/tools.py` and add it to `TOOLS`.

## UI style

The app is mobile-first and dark-only, with a sporty look: ball orange on near-black.

Tokens (`frontend/app/globals.css`, Tailwind v4 `@theme`):
- Colors: `ink` #07090d (page background), `panel` #0e1218 (cards and inputs), `line` (white 9%, borders), `fg` #eef0f5, `muted` #8f97aa, `accent` #ff6b2c (ball orange), `accent-hot` #ff8547 (hover).
- Use token classes (`bg-panel`, `border-line`, `text-muted`, `bg-accent`). Don't use raw hex values.
- Fonts: Barlow for body text and Barlow Condensed for display, both loaded with `next/font` in `layout.tsx`.
- Utilities:
  - `headline`: condensed 800 italic uppercase. Use it for headings, primary buttons and big numbers.
  - `eyebrow`: small, tracked, uppercase orange label above a title.
  - `hatch`: static diagonal hatch on the upload button.
  - `stripes`: animated stripes on video placeholders while a job runs. Turned off under `prefers-reduced-motion`.

Components (`frontend/app/ui.tsx`):
- Reuse `inputClass`, `labelClass`, `buttonClass` / `buttonBaseClass`, `secondaryButtonClass`, `PageIntro`, `RadioTiles`, `SubmitBar`, and the inline SVG icons (stroke 2.2, `currentColor`).
- Don't add a component or icon library.

Layout and shape:
- Content width is `max-w-5xl` with `px-4`; forms are `max-w-xl`. The header is sticky and blurred, and the active nav link is an orange pill.
- Corner radius grows with element size: `rounded-xl` for inputs and tiles, `rounded-2xl` for buttons and small panels, `rounded-3xl` for cards and video frames.
- Accent elements get a soft orange glow shadow.

Mobile:
- Tap targets are at least `h-12`; the primary button is `h-14`.
- On long forms, the submit button sits in a sticky `SubmitBar` at the bottom, which fills as the upload progresses.
- Respect safe-area insets (`env(safe-area-inset-*)`) and use `svh`/`dvh` units for heights.

Video:
- Breakdown results are vertical (9:16); Auto-Cut results are landscape until the clip's own aspect ratio loads.
- Always use `playsInline`.

Accessibility:
- Keep the orange `:focus-visible` outline. Use `aria-live` for upload and job status, `role="progressbar"` on progress bars, and `role="alert"` on errors.

Copy:
- Short and direct, in second person, and plain about what happens: "Cut the dead time.", "Keep the sound on, that's how we find the rallies."
- Errors say what to do next.

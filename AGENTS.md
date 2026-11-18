# TTSkill

AI coaching for table tennis from the video on your phone, built for HackPrinceton Fall 2026.

- **Target user:** amateur players who want to learn from pros and review their own matches. They are on their phones, often courtside, uploading video they just filmed or pasting a YouTube link.
- **Tracks:** Entertainment, Amazon Practical AI, ChatOverflow, LangChain deepagents.

## Features

Every video input accepts an upload or a pasted YouTube link (watch, youtu.be, Shorts or /live/; fetched at <=720p by `app/download.py` and deleted after the job). Bad input is stopped on the form and again by the API, never in the pipeline; the limits are in `shared/limits.json` (see [Input validation](#input-validation)).

**Which one is you?** (Breakdown, Match, Coach; `frontend/app/player-picker.tsx`, `backend/technique/people.py`). The browser draws 12 frames spread over the video and `/players/detect` finds the people in them (duplicates merged, background people set aside). Nobody: a message and "Analyse anyway". One player: analysed, with "Change player". Two or more: the picker. A browser that can't read the file (Chrome without HEVC) sends the video instead and the job reuses it (`staged`). "Only me in the video" (Coach, Breakdown) skips all this and follows whoever plays the most (`people.most_active`). Each lookup logs its frames, people per frame and time split in the browser console, Next.js and the backend.

**TT Coach** (`/coach`). One plain-language request plus a video. A fixed pipeline in code (`agent/fixed.py`) and one structured Claude call (`agent/brief.py`, `COACH_MODEL`):
- rallies from the sound (cached per video); the pose-based play check and the highlight reel run in the background
- the seed, then pose at the strokes (`technique/hitpose.py`): the busiest rallies scanned at 1 fps, every stroke onset probed with 3 frames, full rate only around the fastest strokes (cached per video and player)
- the coached stroke: the player's own, seen whole, inside the frame and big; a 2.4 s clip of it gives the key moments, angles at contact, height and the pro match (the pros' video compiles in the background)
- one Claude call with prompt caching on the static instructions, style guide and pro reference numbers; it writes the summary and the 3 cards, then the coached stroke is rendered at 720x1280
- outputs reach the job page as they finish; `job.timings` holds every stage and the call's tokens and cost (`backend/timing.py`, `scripts/time_coach.py`)

Without `ANTHROPIC_API_KEY` the offline cards are used. `COACH_ENGINE=agent` runs the earlier LangChain deepagents agent instead (planning with `write_todos`, subagents `clip_analyst`, `player_matcher`, `coach_writer`, six tools); if the pipeline itself fails, the old fixed plan of those tools finishes the job.

**Technique Breakdown** (`/breakdown`). A clip of a player the user admires, or a text description of their training, plus an optional stroke type: forehand topspin, forehand drive, forehand loop vs backspin, backhand topspin, backhand flick, backhand push, chop or serve. Blank means auto-detect from the swing or the text.
- The result is a vertical 1080x1920 coaching video in the measured style from `style/swift_style.json`:
  - a persistent header
  - 3 two-word cues, each in its own colour, with a slow-motion lead-in and a freeze frame
  - a bat-hand ring and trail in the cue's colour
  - a recap, then a practice drill
- Pipeline: pick a window → 720p proxy → MediaPipe pose → stroke type → key moments (the swing direction depends on the stroke type) → analyzer → `StrokeBreakdown` → render.
- The analyzer uses Claude vision (structured output) when `ANTHROPIC_API_KEY` is set, and the offline per-stroke templates otherwise. Text-only input renders cards only.

**Find my pro match** (`/match`). The user's swing, forehand or backhand, their grip (shakehand by default, or penhold), and an optional height in cm or ft/in; otherwise height is estimated from the table (76 cm high, 274 cm long).
- Only pros with the same bat hand are considered. A weighted distance on height and body proportions picks the top 3. DTW on the stroke's joint-angle curves says where the user's form differs from each.
- The result: 3 pros with scores and notes, plus one video of their cached breakdowns.
- Pros with the user's grip rank first; others only fill the top 3.
- A pro card can carry warnings: the pro's `equipment_notes` (Sabine Winter's anti-spin backhand), and for penhold pros, when the user isn't penhold, that their backhand differs from shakehand.
- Pro data lives in `backend/data/players/`: 20 players today (3 penhold), roadmap 100.

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
| `frontend/lib/jobs.ts` | Server-only job client with three modes: **proxy** to FastAPI when `BACKEND_URL` (or, failing that, `NEXT_PUBLIC_API_URL`) is set; **stub** (in-memory jobs with fake progress) when it is unset; **demo** (`DEMO_MODE=1`, every submission returns the cached results in `lib/demo-jobs.json` + `public/demo/*.mp4`). |
| `frontend/lib/submit.ts` | Client upload via XHR, which reports upload progress. Posts to `/api/jobs/<kind>`, or straight to the backend when `NEXT_PUBLIC_API_URL` is set (`jobEndpoint`). Also holds the `Job` and `Breakdown` types. |
| `backend/app/main.py` | FastAPI endpoints. They validate input, save the upload, create the job and start a background task. CORS allows `https://*.vercel.app`, `https://*.trycloudflare.com` and `http://localhost`. |
| `backend/app/pipelines.py` | `run_autocut` and `run_breakdown`. Plain functions that update the job record as they go. |
| `backend/app/rally.py`, `cut.py` | Auto-Cut: hit and rally detection; padding, cutting and joining segments. |
| `backend/app/download.py` | Pasted YouTube links (watch, youtu.be, Shorts) via yt-dlp: probed before the job starts (private, unavailable, over 3 min fail on the form), downloaded at <=720p into the job folder, deleted after the pipeline runs. |
| `backend/app/jobs.py` | Job records as JSON at `backend/data/jobs/<id>/job.json` (written atomically). Results go to `result.mp4` in the same folder. `run()` wraps every background pipeline; `get()` fails jobs orphaned by a restart. |
| `backend/technique/` | Breakdown pipeline (`pipeline.py`, `pose.py`, `analyze.py`, `render.py`, `schema.py`). Has its own CLI (`python -m technique`) and its own [README](backend/technique/README.md). |
| `backend/technique/strokes.py` | Stroke types (forehand topspin, drive, loop vs backspin, backhand topspin/flick/push, chop, serve): swing direction for key moments, coaching focus for the Claude prompt, and auto-detection from pose features or text. |
| `backend/style/` | Teaching-style profile. `fetch_refs.py` downloads reference videos into git-ignored `backend/data/style_ref/` (never commit or serve them), `analyze_refs.py` measures pacing, freeze frames, slow motion and text layout, `build_style.py` writes `swift_style.json`. `technique/style.py` loads it for the renderer (pacing, phase colours), the offline templates and the Claude prompt. |
| `backend/technique/fonts/` | Barlow and Barlow Condensed (SIL OFL, see `OFL.txt`) so videos match the app's type. |
| `backend/players/` | Find my pro match. `body.py` (limb ratios, stance width, joint-angle curves from a pose track), `table.py` (height from the table: 76 cm high, 274 cm long), `match.py` (same bat hand, the user's grip first, weighted distance on height and proportions for the top 3, warnings for anti-spin and penhold backhands, DTW on the stroke's angle curves for form differences), `compile.py` (one video of the matched pros' cached breakdowns), `build.py` (searches YouTube, cuts ~8 s clips at 720p, runs the pipeline, caches each breakdown, deletes raw downloads; resumable, `--local` adds a clip from a file). |
| `backend/data/players/` | `players.json` (20 pros: `height_cm` + `height_source`, `bat_hand`, `grip`, optional `bat_hand_source`, `equipment_notes` and `aliases`, clip references) and `profiles.json` (computed numbers) are committed; clips and rendered videos in the same folder are git-ignored. A height whose sources disagree says "(approximate)" in `height_source`. `aliases` replaces the builder's title-matching guesses when a family name alone is ambiguous (Lebrun, Winter). |
| `shared/limits.json` | Every input limit: height, upload type/size/length/resolution, link length per page, text lengths, Auto-Cut settings, the allowed choices, and the pose visibility floor. Read by `frontend/lib/validate.ts` and `backend/limits.py`. |
| `backend/app/validate.py` | The API's input checks against those limits, including ffprobe on uploads (video track, length, resolution). |
| `frontend/lib/validate.ts` | The same checks for the forms' inline errors and the Next.js routes' 422s. Link-shape checks are in `lib/youtube.ts`. |
| `backend/agent/` | TT Coach. `fixed.py` is the default pipeline (parallel steps, partial results), `brief.py` its one cached, structured Claude call. `coach.py` runs it, or the deepagents agent with `COACH_ENGINE=agent`, and the old fixed plan if the pipeline fails. `tools.py` holds the six tools, bound to one job, wrapping the existing pipelines. |
| `backend/technique/hitpose.py` | Pose at the strokes for Coach: rally scan at 1 fps, 3-frame probes at every stroke onset, 30 fps windows around the fastest; the coached-stroke choice. |
| `backend/app/cache.py`, `backend/timing.py` | The per-video cache (by content hash, `backend/data/cache/`) of rallies, seed and stroke pose; the per-job stage and Claude-cost timings. |
| `backend/technique/tools.py` | The same steps as plain functions (`TOOLS`), ready for a future deepagents orchestrator. |
| `scripts/refresh_demos.py` | Re-runs the four demo jobs on the committed Before clips (`frontend/public/examples/*-before.mp4`) and exports `lib/demo-jobs.json`, `coach-example.json`, `demo-assets.json` and the After videos together. Don't hand-edit those; `frontend/test/demo.test.ts` checks they come from one refresh. |
| `samples/` | Local test videos. Git-ignored. |

### API

| Method | Path | Body |
| --- | --- | --- |
| POST | `/jobs/autocut` | multipart: `video` or `url` (YouTube link), `mode` (`highlights`/`full`), `top_n`, `threshold`, `gap`, `min_hits` |
| POST | `/jobs/breakdown` | multipart: `stroke_type` (optional, blank = auto-detect), `text` and/or `video`, `staged` or `url`, `player`, `hand` (`auto`/`left`/`right`), `player_time` + `player_box` (tapped player), `only_me` (`1`); legacy `stroke` still accepted |
| POST | `/jobs/coach` | multipart: `request`, `video`, `staged` or `url`, `player_time` + `player_box`, `only_me` (`1`) |
| POST | `/players/detect` | "Which one is you?": `frames` (JPEG/PNG, max 16) + `times`, or `video` (the browser couldn't read it: ffmpeg frames, answer carries a `staged` token for the job), or `url`, or `job` (Change player). Answers `candidates`, `others` (background: `still`/`far`/`small`), `frame`, `frames` (people per frame) and `timing` |
| POST | `/jobs/{id}/rerun` | `player_time` + `player_box`: the same job following another player |
| GET | `/jobs/{id}/files/{name}` | Videos the coach made (`highlights.mp4`, `breakdown.mp4`, `pro_matches.mp4`) |
| POST | `/jobs/match` | multipart: `video`, `staged` or `url`, `stroke` (`forehand`/`backhand`), `grip` (`shakehand`/`penhold`, default shakehand), `height_cm` (optional), `hand`, `player_time` + `player_box` |
| GET | `/jobs/{id}` | Job record |
| GET | `/jobs/{id}/result` | Result MP4 |
| GET | `/health` | `{"ok": true}` |

The frontend exposes the same paths under `/api/jobs/...`. FastAPI's interactive docs are at http://localhost:8000/docs.

The job record has these fields:
- Always: `id`, `kind`, `status` (`queued`/`running`/`done`/`failed`), `progress` (0–1), `message`, `params`, `resultUrl`.
- Auto-Cut adds `rallies`, and `warning` when fewer than 2 rallies were heard (the job is still `done`).
- Breakdown adds `breakdown`, `videoPrompt`, `analyzer`, `batHand` and `window`.
- Match adds `matches` (each with `grip` and `warnings`) and `you`.

Invalid input is answered with a 422 and a message the user can act on, as `{detail}` from FastAPI and `{error}` from the Next.js routes.

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
- `.venv/bin/python -m players.build` builds the pro profiles. It's resumable and stops when YouTube rate-limits; re-run it later. `--only ID ...` builds some players, `--local PLAYER STROKE FILE URL TITLE` adds one clip from a file.
  - Run one build at a time. Each run rewrites `players.json` and `profiles.json` whole from what it loaded at start, so two runs (or editing the roster during a run) lose each other's changes.
  - Each worker takes about 3 GB of RAM (MediaPipe plus rendering). On an 8 GB machine use `--workers 1`, and don't run the test suite at the same time.
- `.venv/bin/python -m style.fetch_refs && .venv/bin/python -m style.analyze_refs && .venv/bin/python -m style.build_style` rebuilds the coaching-style profile.

Space YouTube requests out. Never work around its bot check by switching clients or using someone's cookies; wait and retry instead.

### Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `BACKEND_URL` | frontend | FastAPI URL for the Next.js routes. Unset means `NEXT_PUBLIC_API_URL`, then stub mode. `make frontend` sets it to `http://localhost:8000`. |
| `NEXT_PUBLIC_API_URL` | frontend | The backend's public URL, e.g. a Cloudflare tunnel. When set, the browser posts jobs and loads result videos straight from it (Vercel Functions cap bodies at 4.5 MB), and the routes use it when `BACKEND_URL` is unset. Inlined at build time: redeploy after changing it. Leave it unset locally. |
| `DEMO_MODE` | frontend | `1` makes every submission return the cached demo jobs. |
| `ANTHROPIC_API_KEY` | backend | Enables the Claude vision analyzer (Breakdown) and Coach's coaching call. Without it, the offline analyzer and offline cards are used. `make dev` doesn't read `backend/.env`; export the key or put it in your shell. |
| `COACH_MODEL` | backend | Claude model for Coach's one call (default `claude-sonnet-5-5`). The deep agent (`COACH_ENGINE=agent`) uses `claude-opus-5-5`. |
| `COACH_EFFORT` | backend | Effort for that call (default `medium`: 8.7 s vs 19-22 s at the model default, same fixes; blank = model default). |
| `COACH_ENGINE` | backend | `agent` runs the deepagents agent instead of the fixed pipeline (Phase 0 baseline). |
| `TECHNIQUE_MODEL` | backend | Claude model id for the analyzer (default `claude-opus-5-5`). |
| `POSE_MODEL_PATH` | backend | Local `pose_landmarker_full.task`. Otherwise it is downloaded once to `~/.cache/ttskill/`. |
| `TTSKILL_SAMPLE` | tests | Sample video for the technique end-to-end test. |

Frontend variables go in `frontend/.env.local`; see `frontend/.env.example`. Never commit secrets: `.env*.local` is git-ignored.

### Deploy: Vercel + a Cloudflare quick tunnel

```bash
make backend                                    # FastAPI on :8000
cloudflared tunnel --url http://localhost:8000  # prints https://<random>.trycloudflare.com
```

On Vercel, set the root directory to `frontend` and `NEXT_PUBLIC_API_URL` to the tunnel URL, then redeploy.
- The tunnel URL changes every time `cloudflared` restarts. Update the variable and redeploy, since it is baked into the build.
- Submissions then go straight to the backend, so `DEMO_MODE` no longer answers them; the `/jobs/demo-*` pages still work.
- `make backend` reloads on file saves, which fails running jobs. Don't edit backend code during a demo. A reload waits at most 5 s for running work (`--timeout-graceful-shutdown 5`); without it a reload waited for a running job (minutes) and every new request queued behind it.

## Tests and checks

```bash
make test                                              # backend (pytest) + frontend API routes (vitest)
cd backend && .venv/bin/python -m pytest tests/test_api.py -q   # a single file
cd frontend && npm test                                # Next.js API routes only
cd frontend && npx tsc --noEmit                        # type check
cd frontend && npm run build                           # production build (stop `next dev` first: they share .next)
```

- `backend/tests/test_api.py` covers every FastAPI endpoint: validation (422s, bad uploads on every endpoint), what each one schedules, job reads, result and file serving, the Auto-Cut warning, and the end-to-end text and video breakdowns. `backend/tests/test_validate.py` covers the checks themselves: height, choices, ranges, text, upload names, ffprobe, link shapes and metadata, the pose visibility check. `backend/tests/conftest.py` makes small real clips with ffmpeg (`media`, `upload` fixtures). `frontend/test/validate.test.ts` and `youtube.test.ts` cover the same checks on the frontend. `frontend/test/api.test.ts` covers every Next.js route in stub, proxy (fetch mocked) and demo modes. It fails if a new `route.ts` isn't added to its table.
- Background jobs go through `jobs.run(...)`, so a job always ends `done` or `failed`. A job left `running` by a server restart (`uvicorn --reload` on a file save, a crash) is reported as failed with a "server restarted" message, because `jobs.ACTIVE` only holds jobs this process is working on. This assumes one worker process.
- Run only one `make dev` per checkout. Two `next dev` servers share `frontend/.next` and break each other's routes.

- Tests that need a real match skip unless `samples/IMG_8782.MOV` exists, or `TTSKILL_SAMPLE` is set for the technique test.
- Render and cut tests need ffmpeg. Pose tests need `libegl1`/`libgles2`.
- Add a test with each backend change. Pure functions such as `padded_segments` and `group_rallies` should be tested without video files.

## Input validation

The limits live in `shared/limits.json`; change them there and both sides follow.

| Input | Rule | Where it's checked |
| --- | --- | --- |
| Height | 100–230 cm, or the same range in ft/in (3 ft 4 in to 7 ft 6 in). Digits only: text, negatives, `1e2`, `nan` are rejected. | form, route, API |
| Upload | MP4, MOV, WebM or MKV; at most 500 MB; 2 s to 10 min; a real video track (cover art doesn't count); at least 240 px on the short side (else "re-record") | type and size: form and route; length and resolution: form when the browser can read the preview; everything: API (ffprobe) |
| Link | YouTube watch, youtu.be, Shorts or /live/. Playlists and channel links get their own message. Private, members-only, age-restricted and live videos are refused. Length: 3 min on Breakdown, Match and Coach; 60 min on Auto-Cut. | shape: form and route; the rest: API (`download.probe`) |
| Stroke type, bat hand, grip, mode | One of the form's options | route, API |
| Coach request | 1–1000 characters after trimming. Blank requests are ignored: the submit button stays disabled. | form, route, API |
| Player name, training text | 80 and 5000 characters | form, route, API |
| Auto-Cut settings | Rallies in the reel 1–20, hit threshold 1.5–10, max gap 0.5–5 s, min hits 2–20 | form, route, API |
| Rallies found | Fewer than 2 is a warning on a `done` job (film closer, less background noise, lower the threshold), not an error | pipeline |
| Player visible | At least 40% of the analysed frames, else the job fails asking for a clearer clip | pipeline, after pose |
| Player frames, only_me, staged | At most 16 frames of 1500 KB; `only_me` is `1` or blank; `staged` is a token from `/players/detect` (used once, kept 2 h) | route, API |

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
  - Schedule it with `background.add_task(jobs.run, run_<kind>, job["id"], ...)`, never bare, so a crash or a missing final status can't leave the job running.
- Import heavy modules (MediaPipe, OpenCV) inside the pipeline function, so the API starts fast.
- Endpoints validate input with `app/validate.py` (or raise `validate.Invalid("...")`), which main.py answers with a 422 and a message a user can act on. Uploads go through `stage_upload()`, so a bad file never creates a job. FastAPI's own type errors (`top_n=abc`) are turned into the same kind of message. The Next.js layer turns FastAPI's `{detail}` into `{error}`.
- After pose extraction, call `pose.require_player(track)`: under 40% of frames with a player, the job asks for a clearer clip instead of rendering a bad video.
- `StrokeBreakdown` in `technique/schema.py` is the contract between analysis, prompting and rendering. If you change it, update the `Breakdown` type in `frontend/lib/submit.ts` to match.
- Hit detection exists in both `app/rally.py` and `technique/audio.py`. Keep the two in step.

Frontend (TypeScript)
- Use strict TypeScript and the `@/` import alias. Add `"use client"` only to components that need state or browser APIs.
- `lib/jobs.ts` is `server-only`. Client code talks only to `/api/jobs/*`, never to the backend directly. The one exception is when `NEXT_PUBLIC_API_URL` is set: uploads (`submitJob`) and result videos go to the backend, because Vercel Functions cap request and response bodies at 4.5 MB. Polling stays on `/api/jobs/*`.
- API routes validate the form first with `lib/validate.ts` and return `invalid(message)` (a 422 with `{ error }`), then delegate to `createJob` / `getJob` / `getResult`.
- Forms show each problem inline next to its field (`FieldError`, `aria-invalid`) and pass `blocked` to `SubmitBar` so the button is disabled until it's fixed. `VideoPicker` checks the file and link itself and reports through `onProblem`. A missing video is still reported on submit.
- Pass the `range` header through on video results; iOS Safari needs it to seek.

Adding things
- **A new job kind:**
  - backend: an endpoint in `main.py` and `run_<kind>` in `pipelines.py`
  - frontend: a route at `frontend/app/api/jobs/<kind>/route.ts`, the kind added to the `Job["kind"]` union, a form page, and handling on `jobs/[id]/page.tsx`
  - a demo entry in `demo-jobs.json` if it should work in `DEMO_MODE`
- **A new limit:** add it to `shared/limits.json`, check it in `backend/app/validate.py` and `frontend/lib/validate.ts` with the same message, and test both sides.
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

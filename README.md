# TTSkill

AI coaching for table tennis, from the video on your phone. HackPrinceton Fall 2026.

**Who it's for:** amateur players who want to learn from pros and review their own matches.

**Tracks:** Entertainment · Amazon Practical AI · ChatOverflow · LangChain deepagents

## Features

| | What you do | What you get |
| --- | --- | --- |
| **TT Coach** (`/coach`) | Type one request, such as "here's my match, show my best rallies and fix my forehand", and add a video or YouTube link. | A deepagents agent (Claude) plans the work and shows its todo list updating live. It runs the tools below and returns the videos plus a short "what to work on". |
| **Technique Breakdown** (`/breakdown`) | Upload or paste a clip of a player you admire, or describe their training. You can pick the stroke type (forehand topspin, drive, loop vs backspin, backhand topspin/flick/push, chop, serve); left blank, it's auto-detected. | A vertical coaching video with a pose skeleton. Each of 3 two-word cues gets its own colour and freeze-frame, followed by a recap and a practice drill. Written by Claude when a key is set, from templates otherwise. |
| **Find my pro match** (`/match`) | Film your swing, pick forehand or backhand and your grip (shakehand or penhold), and optionally enter your height in cm or ft/in. Otherwise it's estimated from the table (76 cm high, 274 cm long). | The 3 pros with the same bat hand who are closest to your height and build (your grip first), each with a similarity score, where your form differs (DTW on joint-angle curves), and one video of their breakdowns. Cards warn when a pro's backhand isn't one to copy: Sabine Winter's anti-spin, and penhold backhands for shakehand players. 20 pros today; *roadmap: 100 players*. |
| **Match Auto-Cut** (`/autocut`) | Upload your match or paste a link. | Every ball contact is heard, rallies are found, and you get the full match with the dead time cut, or highlights ranked by shots per rally. |

Every video input takes an upload **or a pasted YouTube link** (watch, youtu.be or Shorts, fetched at ≤720p).

### Input limits

Checked on the form (inline, with the button disabled), again by the API (a 422 with a message that says what to do), and never left to the pipeline. They're all in [`shared/limits.json`](shared/limits.json).

- **Uploads:** MP4, MOV, WebM or MKV, up to 500 MB, 2 seconds to 10 minutes, with a video track, at least 240p (smaller asks you to re-record).
- **YouTube links:** a single video, not a playlist or channel; public, not age-restricted, not live. Up to 3 minutes for a stroke (Breakdown, Match, Coach) and 60 minutes for a match on Auto-Cut.
- **Height:** 100–230 cm, or 3 ft 4 in to 7 ft 6 in.
- **TT Coach request:** 1 to 1000 characters; a blank request isn't sent.
- **Auto-Cut:** fewer than 2 rallies heard gives a warning with tips (film closer, less background noise), not an error.
- **Pose:** if the player is in less than 40% of the frames, you're asked for a clearer clip instead of getting a bad video.

### How each track is covered

- **Entertainment:** highlight reels of your own rallies and shareable vertical breakdown videos of the pros.
- **Amazon Practical AI:** a phone video in, specific coaching out. Joint angles, body proportions and swing timing are measured, not guessed.
- **ChatOverflow:** TT Coach takes one plain-language request and answers with a plan, the work and the results.
- **LangChain deepagents:** TT Coach is built on deepagents planning, subagents and its virtual file system (below).

## Built with deepagents

**TT Coach** (`/coach`, `backend/agent/coach.py`) is a [LangChain deepagents](https://github.com/langchain-ai/deepagents) agent with Claude (`claude-opus-5-5`) as its model.

- **Planning.** The agent starts with `write_todos`, a short plan for exactly what you asked. The todo list streams into the job record, so the page shows it ticking off live.
- **Subagents.** The main agent delegates with the `task` tool:
  - `clip_analyst` finds rallies, cuts highlight reels and measures pose (`detect_rallies`, `cut_highlights`, `extract_pose`).
  - `player_matcher` finds the closest pros and the form differences (`match_players`).
  - `coach_writer` writes three cards in the coaching style from `backend/style/swift_style.json`, then renders them (`render_breakdown`).
- **Virtual file system.** The agent saves its plan and notes (`/plan.md`, `/rallies.json`, `/pose_summary.json`, `/matches.json`, `/cards.md`, `/notes.md`) in deepagents' in-state file system. Subagents pass results through those files instead of the chat, and the page shows them under "Coach's notes". The agent only gets the file tools; there is no shell.
- **Tools.** `download_url`, `detect_rallies`, `cut_highlights`, `extract_pose`, `render_breakdown` and `match_players` (`backend/agent/tools.py`) are thin wrappers over the same pipelines the classic pages use. Each video a tool makes shows up on the page as soon as it's ready.
- **Fallback.** Without `ANTHROPIC_API_KEY`, or if the agent fails, the same tools run on a fixed plan built from the request, with the same live todo list. The classic endpoints (`/jobs/breakdown`, `/jobs/autocut`, `/jobs/match`) are unchanged.

## How it works

```
Browser ──> Next.js /api/jobs/* ──> FastAPI /jobs/* ──> background pipeline ──> backend/data/jobs/<id>/
```

- **Rallies:** a 2–6 kHz band-pass picks up ball contacts. Contacts are grouped into rallies by the gap between them, then cut and joined with ffmpeg.
- **Technique:** pick a window (the longest rally by sound, or the most motion), run MediaPipe pose, and find the key moments (the stroke type sets the swing direction). Then Claude vision (or a template) writes the cards and the renderer builds the video.
- **Coaching style:** the pacing, card layout and cue naming were measured from a coaching channel's recent videos and Shorts, and are written in our own words in `backend/style/swift_style.json`. The reference videos are never committed or shown.
- **Pro matching:**
  1. Limb ratios and stance come from MediaPipe world landmarks.
  2. A weighted distance on height and proportions (bat hand must match) picks the top 3.
  3. DTW on the stroke's joint-angle curves shows where your form differs.

## Run locally

Needs Node 20+, Python 3.11+ and ffmpeg. On Linux and WSL, MediaPipe also needs the OpenGL ES/EGL libraries.

```bash
sudo apt install -y ffmpeg libegl1 libgles2   # Linux / WSL, one time

make install    # backend venv + npm install
make dev        # frontend on :3000, backend on :8000 (Ctrl-C stops both)
make test       # backend (pytest) and frontend (vitest) tests
```

- **Claude:** set `ANTHROPIC_API_KEY` in the backend's shell to turn on the Claude analyzer and the TT Coach agent. Without it, everything still runs: the templates write the breakdowns and the coach follows a fixed plan.
- **Pro profiles:** run `cd backend && .venv/bin/python -m players.build`. It searches YouTube, cuts ~8 s clips, renders and caches each breakdown, and deletes the raw downloads. It's resumable, and it stops politely if YouTube rate-limits. `--only ID ...` builds some players, `--local PLAYER STROKE FILE URL TITLE` adds a clip you already have. Run one build at a time, and use `--workers 1` on an 8 GB machine (each worker needs about 3 GB).
- **Coaching style:** run `python -m style.fetch_refs`, then `analyze_refs`, then `build_style` to rebuild `swift_style.json`.
- **UI only:** `cd frontend && npm run dev` runs without Python; the API routes then return placeholder jobs.

## Judging demo

Cached results ship with the frontend, so the demo never waits on the pipeline:

- `/jobs/demo-breakdown`: a Ma Long forehand breakdown in the new coaching style.
- `/jobs/demo-autocut`: the top 5 rallies of a 3:35 match, cut into a 49 s highlight reel.
- `/jobs/demo-breakdown`: forehand breakdown video and steps from the technique pipeline, on a clip of Ma Long.
- `/jobs/demo-autocut`: from IMG_8782.MOV, the top 4 rallies by shot count, cut into a 42 s highlight reel (a pre-serve floor-bounce routine is filtered out).

Set `DEMO_MODE=1` for the frontend to make every submission return these results instantly. The files are `frontend/lib/demo-jobs.json` and `frontend/public/demo/*.mp4`.

## API

| Method | Path | Body |
| --- | --- | --- |
| POST | `/jobs/coach` | multipart: `request` (text), `video` or `url` |
| POST | `/jobs/breakdown` | multipart: `stroke_type` (optional), `text` and/or `video` or `url`, `player`, `hand` |
| POST | `/jobs/match` | multipart: `video` or `url`, `stroke` (`forehand`/`backhand`), `grip` (`shakehand`/`penhold`), `height_cm` (optional), `hand` |
| POST | `/jobs/autocut` | multipart: `video` or `url`, `mode` (`highlights`/`full`), `top_n`, `threshold`, `gap`, `min_hits` |
| GET | `/jobs/{id}` | job status, progress, plan, results |
| GET | `/jobs/{id}/result` | result MP4 |
| GET | `/jobs/{id}/files/{name}` | videos made by the coach |

The frontend exposes the same paths under `/api/jobs/...`. Invalid input gets a 422 with a readable message.

## Layout

```
frontend/          Next.js (App Router, TypeScript, Tailwind). Deploy to Vercel with root directory = frontend.
backend/app/       FastAPI endpoints, job store, YouTube links, rally detection, cutting.
backend/technique/ Technique pipeline: pose, stroke types, analyzer (Claude/offline), renderer.
backend/style/     Coaching-style profile (swift_style.json) and the scripts that measure it.
backend/players/   Find my pro match: body profile, table height, matching, profile builder.
backend/agent/     TT Coach deep agent and its tools.
shared/limits.json Input limits, read by both the frontend and the backend.
backend/data/      Local data (git-ignored), except players/players.json and players/profiles.json.
```

See [AGENTS.md](AGENTS.md) for conventions and how to extend each part.

## Known limits

- Vercel functions cap request bodies at about 4.5 MB, so large match uploads should go straight to the backend once it's hosted. Pasting a YouTube link avoids the limit.
- YouTube sometimes shows a bot check to busy IPs. Link downloads then fail with a clear message ("upload the file instead"), and the profile builder stops until a later re-run.
- Height from the table is an estimate (about ±10 cm). Entering your height gives better matches.
- Pro heights and bat hands come from public sources and are listed per player in `players.json`. Seven heights are marked approximate where sources disagree (for younger players, by a few cm).
- Uploads are capped at 10 minutes, so a full match goes in as a YouTube link (up to 60 minutes on Auto-Cut) or in parts.

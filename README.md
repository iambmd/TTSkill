# TTSkill

AI tools for amateur table tennis players and coaches. HackPrinceton Fall 2026.

- **Technique Breakdown**: upload a clip of a favorite player (or describe their training), pick a stroke, and get a step-by-step vertical coaching video.
- **Find my pro match**: film your swing, pick forehand or backhand, and get the 3 pros closest to your height, build and bat hand, with a similarity score, where your form differs (DTW on joint-angle curves), and one video of their breakdowns. *Roadmap: 100 players* (the build script scales; 12 today).
- **Match Auto-Cut**: upload your own match. TTSkill hears every ball contact, finds the rallies, and cuts either the full match (dead time removed) or highlights ranked by shots per rally.

## Status

This is the initial scaffold.

| Piece | State |
| --- | --- |
| Frontend pages (landing, Breakdown, Auto-Cut, job page) | Working |
| Next.js API routes (`/api/jobs/*`) | Working; stub jobs when `BACKEND_URL` is unset, proxy to FastAPI when set |
| Backend job endpoints | Working, jobs stored under `backend/data/jobs/<id>/` |
| Rally detection from audio | Working (ported from the prototype) |
| Cutting and concatenating the rallies | TODO |
| Breakdown pipeline (pose, Claude, render) | Stub |
| deepagents wrapper | TODO |

## Built with deepagents

**TT Coach** (`/coach`, `backend/agent/coach.py`) is a [LangChain deepagents](https://github.com/langchain-ai/deepagents) agent with Claude (`claude-opus-5-5`) as its model. You type one request, such as "here's my match, show my best rallies and fix my forehand", and add a video or link.

- **Planning.** The agent starts with `write_todos`, a short plan for exactly what you asked. The todo list streams into the job record, so the page shows it ticking off live.
- **Subagents.** The main agent delegates with the `task` tool:
  - `clip_analyst` finds rallies, cuts highlight reels and measures pose (`detect_rallies`, `cut_highlights`, `extract_pose`).
  - `player_matcher` finds the closest pros and the form differences (`match_players`).
  - `coach_writer` writes three cards in the style from `backend/style/swift_style.json`, then renders them (`render_breakdown`).
- **Virtual file system.** The agent saves its plan and notes (`/plan.md`, `/rallies.json`, `/pose_summary.json`, `/matches.json`, `/cards.md`, `/notes.md`) in deepagents' in-state file system. Subagents pass results through those files instead of the chat, and the page shows them under "Coach's notes". The agent only gets the file tools; there is no shell.
- **Tools.** `download_url`, `detect_rallies`, `cut_highlights`, `extract_pose`, `render_breakdown` and `match_players` (`backend/agent/tools.py`) are thin wrappers over the same pipelines the classic pages use. Each video a tool makes shows up on the page as soon as it's ready.
- **Fallback.** Without `ANTHROPIC_API_KEY`, or if the agent fails, the same tools run on a fixed plan built from the request, with the same live todo list. The classic endpoints (`/jobs/breakdown`, `/jobs/autocut`, `/jobs/match`) are unchanged.

## Layout

```
frontend/   Next.js (App Router, TypeScript, Tailwind). Deploy to Vercel with root directory = frontend.
backend/    FastAPI. app/rally.py (detector), app/pipelines.py (plain pipelines), app/main.py (endpoints).
samples/    Local test videos (git-ignored). Put IMG_8782.MOV here for the rally test.
```

```
Browser ──> Next.js /api/jobs/* ──> FastAPI /jobs/* ──> background pipeline ──> data/jobs/<id>/
```

## Run locally

Needs Node 20+, Python 3.11+, and ffmpeg.

```
make install
make dev        # frontend on :3000, backend on :8000
make test       # rally detector test (needs samples/IMG_8782.MOV)
```

To try the UI without Python, run `cd frontend && npm run dev`; the API routes then return stub jobs.

## Judging demo

Cached results ship with the frontend, so the demo never waits on the pipeline:

- `/jobs/demo-breakdown`: forehand breakdown video and steps from the technique pipeline, on a clip of Ma Long.
- `/jobs/demo-autocut`: from IMG_8782.MOV, the top 4 rallies by shot count, cut into a 42 s highlight reel (a pre-serve floor-bounce routine is filtered out).

Set `DEMO_MODE=1` for the frontend to make every submission return these results instantly. Files: `frontend/lib/demo-jobs.json` and `frontend/public/demo/*.mp4`.

## API

| Method | Path | Body |
| --- | --- | --- |
| POST | `/jobs/autocut` | multipart: `video` or `url` (YouTube link), `mode` (`highlights`/`full`), `top_n`, `threshold`, `gap`, `min_hits` |
| POST | `/jobs/breakdown` | multipart: `stroke_type` (optional), `text` and/or `video` or `url`, `player`, `hand` |
| POST | `/jobs/coach` | multipart: `request` (text), `video` or `url` |
| POST | `/jobs/match` | multipart: `video` or `url`, `stroke` (`forehand`/`backhand`), `height_cm` (optional), `hand` |
| GET | `/jobs/{id}` | job status, progress, params, detected rallies |
| GET | `/jobs/{id}/result` | result MP4 |

The frontend exposes the same paths under `/api/jobs/...`.

## Known limits

Vercel functions cap request bodies at about 4.5 MB, so large match uploads should go straight from the browser to the backend once it is hosted.

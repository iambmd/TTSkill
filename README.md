# TTSkill

AI tools for amateur table tennis players and coaches. HackPrinceton Fall 2026.

- **Technique Breakdown**: upload a clip of a favorite player (or describe their training), pick a stroke, and get a step-by-step vertical coaching video.
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
- `/jobs/demo-autocut`: from IMG_8782.MOV, the top 5 rallies by shot count, cut into a 49 s highlight reel.

Set `DEMO_MODE=1` for the frontend to make every submission return these results instantly. Files: `frontend/lib/demo-jobs.json` and `frontend/public/demo/*.mp4`.

## API

| Method | Path | Body |
| --- | --- | --- |
| POST | `/jobs/autocut` | multipart: `video`, `mode` (`highlights`/`full`), `top_n`, `threshold`, `gap`, `min_hits` |
| POST | `/jobs/breakdown` | multipart: `stroke`, `text` and/or `video`, `player` |
| GET | `/jobs/{id}` | job status, progress, params, detected rallies |
| GET | `/jobs/{id}/result` | result MP4 |

The frontend exposes the same paths under `/api/jobs/...`.

## Known limits

Vercel functions cap request bodies at about 4.5 MB, so large match uploads should go straight from the browser to the backend once it is hosted.

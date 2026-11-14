# Technique breakdown pipeline (Feature A)

Turns a table tennis clip (or a text description of a player's training) into a
vertical 1080x1920 coaching video: title card, three numbered steps with slow-mo and
freeze frames at each key moment, a glowing pose skeleton on the player, a bat-hand
marker with trail, callout labels, and a "keys" summary card.

```
video ─► pick window ─► 720p clip ─► MediaPipe pose ─► key moments ─► analyzer ─► StrokeBreakdown
           (ball-hit sounds,                            (swing peak lined     (Claude vision    │
            else pose motion)                            up with a hit sound)  or offline)       │
                                                                                                 ├─► video_prompt.json  (text-to-video prompt; no paid API wired yet)
                                                                                                 └─► breakdown.mp4      (pose-overlay render)
text  ─► analyzer ─► StrokeBreakdown ─► video_prompt.json + card-only breakdown.mp4
```

## Run

```bash
cd backend
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r technique/requirements.txt          # Linux also needs libegl1 + libgles2 for MediaPipe
python -m technique --video ../samples/IMG_8782.MOV --stroke forehand --out data/jobs/demo
python -m technique --text "Fan Zhendong flicks with a high elbow..." --stroke flick \
    --player "Fan Zhendong" --out data/jobs/text-demo
```

Options: `--analyzer auto|claude|offline`, `--start/--end` to force a window (seconds),
`--window 8` for the auto window length, `--player NAME`.

On the 3.5-minute sample (`IMG_8782.MOV`) it picks the longest rally (53.7-66.3 s, 17 hits),
and finishes in about 40 s on 4 CPU cores, producing a 15 s video.

## Environment

| Variable | Needed | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | optional | Enables the Claude vision analyzer. Without it the offline analyzer runs. |
| `TECHNIQUE_MODEL` | optional | Claude model id (default `claude-sonnet-5-5`). |
| `POSE_MODEL_PATH` | optional | Local `pose_landmarker_full.task`; otherwise downloaded once to `~/.cache/ttskill/`. |

No paid text-to-video API is used. `video_prompt.generate_video()` is the hook for one later
(Nova Reel, Veo, ...); it returns `None` for the default provider `none`.

## Outputs (in `--out`)

| File | What |
|---|---|
| `result.json` | Manifest: window used, analyzer, key times, paths below |
| `breakdown.json` | `StrokeBreakdown` (see `schema.py`): player, stroke, handedness, headline, grip, stance, swing_path, contact_point, follow_through, steps[3] {title, lines[2], highlight_words, key_time_s, callouts} |
| `video_prompt.json` | `prompt` (≤512 chars), `prompt_long`, `negative_prompt`, `shots[3]`, `aspect_ratio` |
| `pose_summary.json` | Bat hand, swing count, joint angles at each swing |
| `breakdown.mp4` | The rendered 1080x1920 H.264 video |
| `clip.mp4` | The 720p window that was analysed (`key_time_s` is relative to this) |

## Using it from the API / agent

```python
from technique.pipeline import run_video, run_text
res = run_video(str(video_path), str(job_dir), stroke, player or None,
                progress=lambda msg: jobs.update(job_id, message=msg))
# res["outputs"]["overlay_video"] -> copy/rename to job_dir / "result.mp4"
```

`technique/tools.py` exposes the same steps as plain functions (`TOOLS`) for the
LangChain deepagents orchestrator: `technique_breakdown`, `technique_from_text`,
`find_rallies`, `extract_pose`, `analyze_technique`, `render_breakdown`.

## Tests

```bash
cd backend && pytest technique/tests      # ~7 s, no network; the sample test skips if the video is absent
```

# Detection eval harness

Measures the rally/hit detectors against hand-labeled ground truth. Labels are committed
(`eval/labels/*.json`); the videos they describe live in git-ignored `samples/`:

- `samples/coach_demo.mp4` — one continuous ~148 s training session (one scene, near
  player = the teal "CHINA" shirt player, assumed to be the user).
- `samples/match_b.mp4` — a ~140 s CapCut highlights montage: ~18 rally clips across
  4 gyms with hard cuts, the user sometimes near, sometimes far, and a CapCut outro
  card with music at the end. A deliberately hostile re-identification test.

Both were recovered from cached job uploads (`backend/data/jobs/`). Labels were made by
visual review: 2 fps contact sheets for span boundaries, plus a spectrogram + video frame
sheet for each of the 615 detected onsets. Rally bounds are serve to last contact,
about ±0.4 s (±0.7 s around montage cuts).

```bash
cd backend
.venv/bin/python -m eval.run           # audio-only detector
.venv/bin/python -m eval.run --pose    # + the floor-bounce pose filter (slow)
```

## Baseline (before the detection rework)

Defaults: threshold 3.0, gap 1.6 s, min_hits 4. The `--pose` floor-bounce filter changes
nothing on either video (its crouch heuristic never fires here), so these numbers are the
production path. Rally match = IoU ≥ 0.5.

| video | rally P | rally R | F1 | merges | splits | false rallies | onset play-precision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| coach_demo | 0.333 | 0.364 | 0.348 | 0 | 1 | 3 | 0.657 |
| match_b | 0.333 | 0.278 | 0.303 | 0 | 1 | 1 | 0.876 |

The headline failures, confirmed by the labels:

- A third of coach_demo's onsets are not play at all (ball retrieval, pre-serve
  bounces, far-court noise). The detector reports rallies at 11.5–15.2 s (the player is
  walking after a ball) and 144.5–148.5 s (the table is empty; a neighbouring court is
  playing).
- Soft push rallies (17–22 s) sit under the fixed 3.0 onset threshold and are missed.
- The montage's CapCut outro music at 138–140 s produces onsets.

## Datasets

| dataset | status | license | use |
| --- | --- | --- | --- |
| [OpenTTGames](https://lab.osai.ai) | direct download, no signup; markup zips + test videos in `data/openttgames/` (git-ignored); raw videos deleted after feature extraction | CC BY-NC-SA 4.0 | 120 fps ball x/y + bounce/net events: hit-gap calibration (stroke→stroke median 0.65 s, p5 0.34, p95 1.10; stroke→bounce median 0.32 s), video-side checks. **No audio track**, so it cannot train the audio classifier. |
| [Extended OpenTTGames](https://github.com/moamal01/table_tennis_data) | annotations on GitHub | CC BY-NC-SA 4.0 | 1,738 labeled strokes on the same videos (forehand/backhand × loop, push, block, flick, serve, chop, smash): stroke classifier templates. |
| TTStroke-21 (MediaEval) | **gated**: per-user usage agreement via task registration | custom | skipped; Extended OpenTTGames + @swift_TT shorts cover the classes. |
| [P2ANet](https://github.com/Fred1991/P2ANET) | **gated**: Baidu pan, key by emailing the author; archive deprecated | repo says MIT, data gated | skipped. |
| @swift_TT YouTube Shorts | yt-dlp, titles name the stroke | reference/training only; no redistribution, no branding in output | extra labeled swings for the stroke classifier. |

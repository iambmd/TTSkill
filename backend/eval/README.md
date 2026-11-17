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

## Resumed evaluation (2026-11-16)

Handoff verified: `main` and fetched `origin/main` were `30a204d8fda4e343f5af0958c9c6534c200f7abb`.
The uncommitted rally/filter/caller changes, onset model and trainer were present.
Both samples exist; the original `IMG_8782.MOV` and cached job folders `4c0fa52e` /
`4d3b268c` do not. `match_b` is a montage substitute, not IMG_8782.
The corrected coach_demo second span is **16.5–33.2 s** for every comparison below.

All results below are **development/tuning**, not held-out. Both clips informed Claude's
thresholds and its original model. The labels provide play windows, not individual paddle,
table, floor or shoe contacts. Consequently **contact-level hit precision and recall are
blocked**; the onset column is only the fraction inside a play window (±0.3 s). It cannot
establish recall or contact-type accuracy. Teal-shirt = provisional player identity.

| path / clip | rally P | rally R | merges | splits | false rallies | onset play-window proxy P |
| --- | --- | --- | --- | --- | --- | --- |
| baseline 30a204d / coach_demo | .333 | .364 | 0 | 2 | 2 | .706 |
| recovered handoff / coach_demo | .333 | .545 | 0 | 2 | 3 | .706 |
| current / coach_demo | .368 | .636 | 0 | 2 | 4 | .699 |
| baseline 30a204d / match_b | .333 | .278 | 0 | 1 | 1 | .876 |
| recovered handoff / match_b | .438 | .389 | 0 | 2 | 0 | .876 |
| current / match_b | .333 | .278 | 0 | 2 | 0 | .876 |

IoU ≥ .5, greedy one-to-one matching; defaults threshold=3, gap=1.6, min_hits=4;
all rows include the corresponding production pose filter. The original table above used
an older label revision. Current increases coach_demo recall but still has more false rallies;
match_b removes the false rally without improving baseline recall. This is **not a solved
audio classifier or rally state machine**. Merges are zero under these coarse annotations,
so synthetic break/weak-chain tests provide the direct regression for merging.

Reproduce from the repository root (JSON records include video/label SHA-256):

```bash
cd backend
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.run --pose --baseline 30a204d --output eval/work/baseline.json
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.run --pose --output eval/work/current.json
.venv/bin/python -m eval.train_onset_model --train coach_demo --validate match_b --output eval/work/onset_model.json
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m pytest tests/test_rally.py tests/test_floor_bounce.py tests/test_eval_metrics.py tests/test_coach.py -q
```

The recovered handoff was saved to `/tmp/ttskill-handoff` before editing and evaluated by
loading its `rally.py` and `floor_bounce.py` with the current eval runner. This is a local
recovery artifact, not a reproducible Git revision. Its original tiny model is preserved
locally at `app/onset_model.json`, ignored. Neither model is used for production decisions.
The trainer now requires explicit disjoint train/validation clips and writes only ignored
experimental data. Training on coach_demo, validating on match_b yielded proxy P=.821,
R=1.000, retaining **38/46 non-play onsets**. This is not reliable contact rejection.

What changed and what failed:

- Weak chains no longer override a shorter user-selected gap. Soft onsets still count
  inside strong-onset groups, with bounded .5 s lead-in / 1.2 s tail, partitioned between
  adjacent groups. Prep sounds can still occur within those bounds.
- Removing all edge sounds reduced rally P/R to .294/.455 (coach_demo), .308/.222
  (match_b). Retaining bounded edges recovered those truncated endings.
- Audio timestamps now use the actual integer hop / sample rate. At 22,050 Hz,
  treating 110 samples as exactly 5 ms drifted by ~.27 s over two minutes.
- Technique and Auto-Cut share onset extraction/grouping; Coach now invokes the pose filter.
- Pose swing speed subtracts body translation and rejects large jumps/scale changes.
  Tiny background poses and sustained crouching are rejected; missing model/runtime
  failures preserve audio candidates. Walking must not look like wrist action.
- Concurrent evaluations initially collided on `audio.wav`; those results were discarded.
  Each clip/run now gets a unique temporary directory and has an isolation regression.
- Remaining: noisy strong onsets can still join rallies, background people can still pass
  size filtering, low/occluded pushes can be rejected, montage cuts are not audio events,
  and the ambiguous 80–96 s montage span needs finer annotation.

No new dataset videos were downloaded. Existing ignored `data/` occupies ~276 MB,
well below 10 GB. The cached Extended OpenTTGames README/LICENSE explicitly says
CC BY-NC-SA 4.0; its stroke-side prefixes denote **table side**, not hitting hand.
Its cached `test_2.mp4` is visual-only. Use those annotations for visual timing only.
The earlier statement that swift_TT is licensed for training/reference was a user constraint,
not a verified license grant. Do not treat it as permission for new downloads. No new
TTStroke-21/P2ANet access was obtained; gated datasets remain unavailable here.

## Identity and hand continuation

`extract_pose` now selects a torso appearance once and keeps that identity across
side switches/cuts. It abstains on missing or ambiguous matches. Analysis windows
are seeded from the original video's first frames so a later near opponent cannot
become the coached player. Wide-frame MediaPipe initially hallucinated a high-confidence
body on the table; overlapping half-frame crops plus upright/visibility checks recover
real players. The torso template is fixed to avoid identity drift. Colour-bin smoothing
reduces sensitivity to lighting. Similar shirts, occlusions and unseen clothing remain hard.

The unsmoothed montage experiment retained 113/351 sampled frames (32.2%); a visual
12-frame audit at 1,8,23,30,45,63,70,83,102,109,125,134 s showed 4 correct selections and
8 abstentions. This is sparse visual auditing, **not identity accuracy on the full video**.
No user confirmation of the teal-shirt identity has been received.

Hand estimation now votes from visible wrist speeds in [-.12,+.06] s around audio
onsets, preferring contact evidence in auto mode, retaining colour/motion fallbacks.
Missing neighbours, low-visibility wrists and large body jumps do not supply speed peaks.
If no hand cue is decisive, it asks the user to choose a hand instead of defaulting right.
No contact-hand accuracy claim is possible with the original span-only labels.

A generic Coach request previously forced `forehand`; it now uses `auto`, propagating
the detected wing through the fixed plan. Explicit backhand requests still win.
`eval/regressions/coach_backhand.json` adds a medium-confidence visual wing label near
43.3 s (±.15 s), with no claimed spin subtype or exact audio-contact label. The real-sample
regression verifies player identity and requested-backhand handling. Automatic classification
is a strict expected failure: the pose-derived shoulder projection still calls it forehand.
The label is a development regression, not a held-out evaluation.

```bash
cd backend
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m pytest technique/tests/test_identity.py technique/tests/test_coach_sample.py -q
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m pytest tests technique/tests -q
cd ../frontend
npm test
npm run build
DEMO_MODE=1 npm run start -- --hostname 127.0.0.1 --port 3107
```

Backend verification before the temporal experiment: **285 passed, 5 skipped, 1 xfailed**.
The skips require IMG_8782.MOV or explicit network opt-in. FastAPI TestClient hung under
the execution sandbox even for `/health`; the same test and full suite pass outside it.
Frontend: **111 tests passed**, production build passed. HTTP smoke checks: `/`, `/coach`,
`/breakdown`, `/match`, `/autocut` return 200; cached `demo-breakdown` and `demo-autocut`
job/page flows pass, and their videos plus all nine existing `/examples/*.mp4` return
206 for byte ranges. There are no `demo-coach` or `demo-match` cached job fixtures.

Colour smoothing improved montage retention to **183/351 frames (52.1%)**. Repeating the
same 12-frame visual audit yielded **8 correct selections, 4 abstentions, 0 observed switches**,
including near/far switches at 63/70 s and later gyms at 83/109/125 s. These are tuning
observations on this montage, not a population identity-accuracy claim.

For the **same 12 manually reviewed identity frames**, the baseline track has **4 correct,
7 wrong, 1 abstention**, versus current **8 correct, 0 wrong, 4 abstentions**. Hip boxes
and provisional identity are in `eval/regressions/match_b_identity.json`. These counts
measure identity on the audit frames, not landmark accuracy. Reproduce scoring with:

```bash
cd backend
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -c "from technique import pose; pose.save_track(pose.extract_pose('../samples/match_b.mp4', stride=12), 'eval/work/montage.npz')"
.venv/bin/python -m eval.audit_player --track eval/work/montage.npz
```

Baseline uses `extract_pose`/`save_track` loaded from `git show 30a204d:backend/technique/pose.py`
on the same source at stride 12; the saved track is scored with the same audit command.

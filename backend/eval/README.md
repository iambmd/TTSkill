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

At the rally milestone no new dataset videos had been downloaded; ignored `data/`
occupied ~276 MB. The later visual experiment below added one 488 MB download. The cached Extended OpenTTGames README/LICENSE explicitly says
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

## Visual temporal-model experiment

Reverified [OpenTTGames](https://lab.osai.ai/) and
[Extended OpenTTGames](https://github.com/moamal01/table_tennis_data) on 2026-11-16:
both publish CC BY-NC-SA 4.0. Direct HEAD for `test_7.mp4` returned 200 and
488,378,737 bytes. Downloaded only that file (total peak data directory ~742 MiB),
extracted features, and deleted the new raw video. Existing test_2 and prior local
artifacts were preserved. Generated features/model/manifest are ignored.
`ffprobe` confirmed test_7 also has only 120 fps video, **no audio**.

The cached test_2 annotations contain no backhands. test_7 supplies loop/push/flick/block
examples of both wings. `eval.train_strokes` extracts contact-centred sequences from
separate half-frame crops using table-side annotations. Hands must be visually verified:
in test_7, table-left is right-handed and table-right is left-handed. An initial experiment
estimated hand from motion and flipped one right-side example, so this is now explicit.

```bash
# After verifying the same download link/terms; all commands from repository root:
curl -fL --max-filesize 500000000 https://lab.osai.ai/datasets/openttgames/data/test_7.mp4 -o data/openttgames/test_7.mp4
cd backend
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.train_strokes \
  --video ../data/openttgames/test_7.mp4 \
  --labels ../data/openttgames/extended/table_tennis_data-main/data/raw/game_data/test/test_7.json \
  --left-hand right --right-hand left --max-per-wing 8 \
  --output eval/work/stroke_templates.json
.venv/bin/python -m pytest technique/tests/test_temporal.py -q
```

The temporal classifier compares 21-frame sequences of torso-normalized wrist/elbow
position and elbow angle by banded DTW. It abstains for low pose visibility, missing
classes, distant matches or margins below 20%. It only estimates forehand/backhand;
it does **not** establish topspin/drive/push/block/flick/serve subtype accuracy. The
existing subtype heuristics remain. `TTSKILL_STROKE_MODEL=/absolute/path/to/model.json`
is an explicit experimental opt-in; **leave it unset for production**.

Training uses 8 forehand + 8 backhand test_7 examples. Despite the dataset filename,
those examples are **training data** here. coach_demo is separate from training but is
already a development/tuning clip, so it is not called held-out. On the reviewed 43.3 s
backhand, nearest-class distances were FH=.797, BH=.678 (margin .149): abstained.
On the reviewed 62.8 s forehand, FH=.525, BH=.334: incorrectly predicted backhand.
This domain-transfer experiment is **not accepted for default production use**, and the
automatic-backhand regression remains xfailed. More reliable wrist/depth tracks and
independent, contact-labelled local strokes are needed before enabling it. No spin-class
accuracy, hit precision/recall, or held-out improvement is claimed.

Final verification after the temporal experiment: **290 backend tests passed, 5 skipped,
1 expected failure** (automatic backhand), in 51.51 s. Frontend remains at 111 passing
tests, successful production build, and the HTTP/range smoke results above.

## Milestone 2: clip-aware rally refinement (2026-11-17)

Continued the uncommitted draft after `2661c16` (Milestone 1); final production code is `94996b7`. Compared that commit and the final production refinement on the **same source files and label bytes**, including the coach_demo 16.5–33.2 s correction. Source and label SHA-256 values match between both JSON reports. All clips informed development; none is held-out. `match_b@coaching-demo` is the 720p encode of the same montage, with the same timeline (140.247 s) and labels, not a third independent recording.

| Clip / version | Rally P | Rally R | F1 | Merges | Splits | False rallies |
| --- | --- | --- | --- | --- | --- | --- |
| coach_demo / Milestone 1 | 0.350 | 0.636 | 0.452 | 0 | 3 | 4 |
| coach_demo / Milestone 2 | 0.412 | 0.636 | 0.500 | 0 | 3 | 1 |
| match_b / Milestone 1 | 0.353 | 0.333 | 0.343 | 0 | 2 | 0 |
| match_b / Milestone 2 | 0.688 | 0.611 | 0.647 | 0 | 1 | 0 |
| match_b@coaching-demo / Milestone 1 | 0.353 | 0.333 | 0.343 | 1 | 1 | 0 |
| match_b@coaching-demo / Milestone 2 | 0.765 | 0.722 | 0.743 | 0 | 1 | 0 |

Rally matches use greedy one-to-one IoU ≥ 0.5, threshold=3, gap=1.6 s, min_hits=4. Contact-level hit precision/recall is **still unmeasurable** without contact labels. The unchanged onset **play-window proxy precision** is .699 / .876 / .874 respectively; these are not classified paddle-contact scores.

Implementation and production checks:

- Crossfades are detected from linearly changing pixels in the same 10 fps frames decoded for the pose check. Found 14 joins on each montage encode and none on coach_demo. Candidates split at joins; pieces within a clip can merge across gaps up to 4 s. No new audio threshold or trained model was introduced.
- Candidates already identified as non-play block those merges. Unsampled gaps cannot supply a wrist-speed vote. The per-clip figure-size comparison drops three neighboring-court false rallies at the end of coach_demo, retaining all seven matched rallies.
- Auto-Cut and Coach pass the user's `min_hits` through refinement. Both use `pick_segments`, which now clamps padding to clip joins so an adjacent clip is not pulled back into a highlight.
- The 720p 27.45–50.15 s candidate previously covered four rallies. It now becomes 27.45–32.48, 33.35–38.99, 39.71–44.45, and 45.00–52.74 s after splitting/regrouping. A real-video crossfade regression and pure regrouping/padding tests cover this behavior.
- The eval loader now gives snapshot modules their own `__file__` and sibling imports. Previously `--baseline 2661c16` failed with `NameError: __file__`; simply importing current sibling modules would also contaminate comparisons after this milestone.

Failed approach: merging every nearby candidate before checking play produced a new 106.99–127.36 s merged rally in the 720p montage. A 114.26–117.35 s ball-retrieval candidate chained two real rallies together through individually short gaps, and its non-play disappeared in the average pose score. Using non-play candidates as barriers removed that merge. The discarded attempt had F1 .500 / .667 / .706 with one 720p merge; it remains locally at `eval/work/milestone2-merge-before-filter.json`.

Remaining cases:

- Continuous recordings still split during quiet play (three split labels in coach_demo); one ball-retrieval false rally remains there.
- Same-camera hard cuts are not detected. A view change at an undetected cut can invalidate the relative figure-size comparison: the real 129.5–132.9 s montage rally is currently rejected as “another court.” Strong appearance/scale changes and global lighting ramps need separate validation before broader use.
- Late starts and low/occluded strokes are still missed. The montage's 80–95.9 s label may contain two rallies; its crossfade near 89 s contributes the remaining measured split. No labels were retimed to fit the detector.
- No hand/stroke classifier or coached-player seeding change is included in this milestone. The backhand auto-detection xfail and the IMG_8782 opponent-seeding issue remain.

Reproduce from the repository root; use one pose-heavy run at a time:

```bash
cd backend
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.run --pose --baseline 2661c16 --output eval/work/milestone2-before.json
MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.run --pose --baseline 94996b7 --output eval/work/milestone2-after.json
ANTHROPIC_API_KEY='' TTSKILL_SAMPLE="$PWD/../samples/IMG_8782.MOV" MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m pytest tests technique/tests -q -rs
cd ../frontend
npm test
npm run build
```

Raw videos and all generated evaluation reports remain ignored. No new downloads or external analyzer calls were needed.

Final checks: **321 backend tests passed, 2 YouTube network tests skipped, 1 known
automatic-backhand xfail**. The IMG_8782 regression still keeps 10/10 labeled play
spans and 0/4 labeled non-play spans. Frontend: **119 tests passed**, production
build passed.

HTTP smoke: both Auto-Cut and fixed-plan Coach completed on the 26–53 s montage
excerpt, each returning four rallies in a 27 s reel. Both result routes served
`206 Partial Content` for byte-range requests. Reproduce from `backend/` with
`MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.smoke_rallies` (external analysis
is disabled by the script; generated jobs and `eval/work/milestone2-smoke.json` are ignored).

The crossfade-only scan also found **zero joins on IMG_8782**, using the same candidate windows and margins as production.

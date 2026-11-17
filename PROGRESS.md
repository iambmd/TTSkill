# Progress: detection and coaching accuracy

Last updated 2026-11-17. Covers Codex's four commits (30a204d..aa32e8f, 2026-11-16) and the
follow-up fixes (f9c9d48..60accf9). Every number below was re-measured on this machine; all
of it is **development data, not held-out**: the same clips informed the thresholds.

## Status by goal

| Goal | Status | Evidence |
| --- | --- | --- |
| a. Floor bounces / shoe squeaks not counted as hits | partial | The pre-serve floor-bounce routine in IMG_8782 (14.4–19.8 s) is dropped by the crouch check (`tests/test_floor_bounce.py`). Within a kept rally, audio still counts every sharp sound: the onset play-window proxy is unchanged (coach_demo .699, match_b .876). Contact-level hit precision/recall needs per-contact labels, which don't exist. |
| b. Merged rallies split; serve prep not counted | partial | merges = 0 on both labelled clips; anchored grouping keeps weak sounds from bridging breaks (`tests/test_rally.py`). Pre-serve span 120.0–122.9 s in IMG_8782 is dropped. Still fails: the 720p coaching demo merges four montage clips (27.4–50.1 s) across crossfades. |
| c. Correct hitting hand + stroke type | partial | Hand: right on every run (bat colour on the coaching demo and the match example; faster-wrist fallback on coach_demo), matching the provisional label. No per-contact hand labels. Forehand/backhand auto-detection still fails on the one labelled backhand (strict xfail). There is no **block** stroke type, and no subtype (drive/topspin/push/flick) accuracy can be measured. |
| d. Coaching tracks you, not your opponent | done (on the evidence available) | match_b identity audit (12 reviewed frames): 8 correct, **0 wrong**, 4 abstained; sampled coverage 52% → 62%. Coach windows: coach_demo 89% of frames with you; 720p coaching demo picks 54.0–60.2 s (you near, 85%), checked against source frames. Find my pro match now uses the same identity. |
| e. Your backhand recognized in coaching | partial | "Fix my backhand" now renders a backhand breakdown (was a Chop). Automatic backhand detection on the labelled 43.3 s backhand still says forehand. |

## Review of Codex's work (2026-11-16)

What it implemented, verified by reading the diffs and re-running:

- **Rally grouping:** strong onsets set boundaries, weak ones only count inside them; correct hop timing; Auto-Cut and Technique share one onset extractor.
- **Non-play pose filter:** presence, swing and crouch checks, also wired into Coach.
- **Torso-colour identity tracker:** half-frame crops; contact-timed hand vote; generic Coach requests no longer forced to forehand.
- **Eval harness:** hand-labelled spans for coach_demo and match_b, plus a 12-frame identity audit.
- **Opt-in DTW wing classifier:** off by default.

Checks:

- **Metrics reproduce exactly.** `eval.run --pose` and `--baseline 30a204d` give the README's tables.
- **No hardcoded or faked results in the pipelines.** The demo JSON is a cache by design (`DEMO_MODE`).
- **Models are honestly labelled as unused.**
  - `app/onset_model.json` is git-ignored and nothing in production calls `play_scores`.
  - The DTW template is opt-in and measured as failing (1 abstain, 1 wrong on 2 strokes).
- **No datasets or weights in git.** Only the public demo MP4s and `rubbers.csv`.
- **The sample-video tests skipped silently.** IMG_8782 was in Windows Downloads, not in `samples/`. With it in place they run and pass.

What was broken:

1. **Coach produced no technique breakdown on any input.** The player was visible in 35%, 35% and 24% of frames, under the 40% floor.
   - The identity tracker abstained on obvious frames: colour distance .5–.75 against a hard .55 cut-off, while the opponent scored .9–1.0.
   - On the montage, the window was the loudest rally, in which you are the far player.
2. **Auto-Cut dropped real rallies on IMG_8782** (21–26, 27–35, 124–129 s). At 5 fps a wide shot from behind scores 0.04–0.13 swing, under the 0.15 floor.
3. **"Fix my backhand" rendered a Chop**, and plan labels read "Measure your auto".
4. **Contact metrics were invented for joints out of frame** ("knees 79°") and measured in pixels (stance 6.4× on a side view).
5. **Uncommitted demo refresh breaks the frontend.** The pages import `lib/demo-assets.json`, which was never exported because Coach failed: 2 vitest failures and 5 tsc errors in the working tree. `main` builds and tests clean (111 tests).

## Fixes (each its own commit on main)

| Commit | Change | Measured effect |
| --- | --- | --- |
| f9c9d48 | Identity accepts a loose colour match (< .8) only when it beats everyone in frame by .15 or continues in place | coach_demo window 35.6% → 82.8% with player; audit still 0 wrong |
| e8b2fe3, 4d35368 | Window = among the 6 busiest rallies, max(whole-body share × player height), seeded with your identity | Coach completes on all 4 test runs (was 0/3); coaching demo window moves from far-player/cut-off rallies to 54.0–60.2 s |
| 84c67d0 | No "auto" in plan labels/summary | |
| 2180c2f | Non-play filter samples 10 fps, swing floor 0.10 | IMG_8782 regression: real rallies kept 7/10 → 10/10, non-play kept 0/4 → 0/4 |
| 8c0d000 | A requested wing returns only that wing's stroke types | |
| e18c6b6 | Knee/stance/elbow omitted when not visible; angles and widths from 3D world points | |
| 60accf9 | Find my pro match uses the same identity and contact-timed hand | Example result unchanged |

Auto-Cut labelled eval (`eval.run --pose`, IoU ≥ .5):

| clip | baseline 30a204d P / R / F1 | Codex aa32e8f | now |
| --- | --- | --- | --- |
| coach_demo | .333 / .364 / .348 | .368 / .636 / .467 | .350 / .636 / .452 |
| match_b | .333 / .278 / .303 | .333 / .278 / .303 | .353 / .333 / .343 |

coach_demo loses one precision point: one more candidate is kept. New regression from visual review of IMG_8782: `eval/regressions/img8782_autocut.json`. Full stack checked (Next.js route → FastAPI → pipeline → ranged result): Auto-Cut on the 3:35 example keeps 20 rallies; the top 4 now include 27.4–35 s.

Tests: backend 303 passed, 2 skipped (network), 1 strict xfail (automatic backhand). Frontend on `main`: 111 passed, `tsc` clean. Data: `data/` 62 MB after deleting a 225 MB raw OpenTTGames video (`test_2.mp4`) that no eval code read; `samples/` holds IMG_8782.MOV and the 720p `coaching-demo.mp4` (both git-ignored).

## What's left

1. **Forehand/backhand and subtype accuracy (goals c, e).** Needs labelled contacts.
   - coach_demo is 640×360 and mostly filmed from behind, so I couldn't label strokes reliably.
   - Lead worth testing: on the two labelled strokes, the wrist's position along the direction of play during the backswing separated them (forehand −0.9 to −1.0 torso lengths behind the hips, backhand +0.7 to +0.9 in front). The shoulder-axis feature called both bat-side (1.4–1.7).
   - Validate on 20+ labelled contacts from a side-on camera before shipping it.
2. **Block stroke type** doesn't exist yet (strokes.py, offline template, frontend `strokes.ts`).
3. **Montage rallies merge across crossfades.** Scene-cut detection doesn't see dissolves (scene score ≈ 0 except the outro card).
4. **Contact-level hit precision/recall** (floor bounces and shoe squeaks inside a rally) needs per-contact labels. Full rally-span labels for IMG_8782 would also let it join `eval.run`.
5. **Coach runs the window scan twice** (pose tool and render), about a minute per job. Reuse the first window.
6. **Uncommitted demo refresh** (`scripts/refresh_demos.py`, README section, 5 frontend files, tests). Decide whether to finish it or drop it.
   - It replaces every public demo with offline-template results.
   - The current Coach example is a Claude-written run that measured the 80–88 s rally, where you are the far player.

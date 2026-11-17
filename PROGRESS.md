# Progress: detection and coaching accuracy

Last updated 2026-11-17. Covers Codex's four commits (30a204d..aa32e8f, 2026-11-16) and the
follow-up fixes (f9c9d48..60accf9), and Milestone 2 below. Every number below was re-measured on this machine; all
of it is **development data, not held-out**: the same clips informed the thresholds.

## Status by goal

| Goal | Status | Evidence |
| --- | --- | --- |
| a. Floor bounces / shoe squeaks not counted as hits | partial | The pre-serve floor-bounce routine in IMG_8782 (14.4–19.8 s) is dropped by the crouch check (`tests/test_floor_bounce.py`). Within a kept rally, audio still counts every sharp sound: the onset play-window proxy is unchanged (coach_demo .699, match_b .876). Contact-level hit precision/recall needs per-contact labels, which don't exist. |
| b. Merged rallies split; serve prep not counted | partial | merges = 0 on both labelled clips; anchored grouping keeps weak sounds from bridging breaks (`tests/test_rally.py`). Pre-serve span 120.0–122.9 s in IMG_8782 is dropped. Milestone 2 splits the 720p 27.4–50.1 s merge at crossfades; measured merges are now zero on both encodes. Quiet continuous-video splits remain. |
| c. Correct hitting hand + stroke type | partial | Hand: right on every run (bat colour on the coaching demo and the match example; faster-wrist fallback on coach_demo), matching the provisional label. No per-contact hand labels. Forehand/backhand auto-detection still fails on the one labelled backhand (strict xfail). There is no **block** stroke type, and no subtype (drive/topspin/push/flick) accuracy can be measured. |
| d. Coaching tracks you, not your opponent | partial | match_b identity audit (12 reviewed frames): 8 correct, **0 wrong**, 4 abstained; sampled coverage 52% → 62%. Coach windows: coach_demo 89% of frames with you; 720p coaching demo picks 54.0–60.2 s (you near, 85%), checked against source frames. Find my pro match now uses the same identity. The later Milestone 1 review found that first-frame seeding selects the opponent on IMG_8782; that remains unresolved. |
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
3. **Crossfade regrouping shipped in Milestone 2.** Hard cuts, continuous-video quiet gaps and false pose rejections remain; see the final section.
4. **Contact-level hit precision/recall** (floor bounces and shoe squeaks inside a rally) needs per-contact labels. Full rally-span labels for IMG_8782 would also let it join `eval.run`.
5. **Coach runs the window scan twice** (pose tool and render), about a minute per job. Reuse the first window.
6. ~~Uncommitted demo refresh~~ **done 2026-11-17**: all four demos re-run with the fixed pipeline
   (`scripts/refresh_demos.py`). The Coach example now measures the user (teal shirt, near
   player, 54.0–60.2 s, right hand from bat colour, 84% visible), checked against source
   frames; before, it measured the 80–88 s rally where the user is the far player. Results
   come from the offline templates and Coach's fixed plan, not Claude-written text.


## Milestone 2: clip-aware rally refinement (2026-11-17)

Commit `94996b7` finishes the crossfade/refinement draft left after `2661c16`, including both production
callers. Rally P / R / F1 at IoU ≥ .5, using the same videos and label bytes:

| Clip | Milestone 1 | Milestone 2 | Merges before → after | Splits before → after |
| --- | --- | --- | --- | --- |
| coach_demo | .350 / .636 / .452 | .412 / .636 / .500 | 0 → 0 | 3 → 3 |
| match_b (480p) | .353 / .333 / .343 | .688 / .611 / .647 | 0 → 0 | 2 → 1 |
| coaching-demo (720p) | .353 / .333 / .343 | .765 / .722 / .743 | 1 → 0 | 1 → 1 |

These are development results. The montage encodes share footage/labels and are not
independent samples. Audio contact classification has not improved: play-window proxy
precision remains .699 / .876 / .874; contact-level P/R is blocked by missing labels.

- Crossfade joins split rallies, and pieces of an edited clip can merge over short gaps.
  Padding is clamped to joins in Auto-Cut and Coach. The 27–50 s four-rally merge is fixed.
- Non-play candidates block merges. The initial merge-first draft created a new
  107–127 s merge through ball retrieval; that approach was rejected and regression-tested.
- Relative figure size removes three neighboring-court false rallies on coach_demo.
- The baseline loader now isolates revision-local modules and supplies `__file__`.
  The eval README records exact commands, complete metrics, and the failed approach.

Still open: quiet continuous-video splits, missing hard cuts, occasional false pose
rejections (including the 129.5–132.9 s montage rally), automatic backhand recognition,
and selecting the correct initial player on IMG_8782. No new data was downloaded.
The already-refreshed website examples were intentionally not regenerated for this step.

Final verification: backend **321 passed, 2 network tests skipped, 1 known automatic-backhand
xfail** with `TTSKILL_SAMPLE` set to IMG_8782. The IMG_8782 regression retains all 10
labeled play spans and rejects all 4 labeled non-play spans. Frontend **119 passed** and
production build passed.

HTTP smoke: both Auto-Cut and fixed-plan Coach completed on the 26–53 s montage
excerpt, each returning four rallies in a 27 s reel. Both result routes served
`206 Partial Content` for byte-range requests. Reproduce from `backend/` with
`MPLCONFIGDIR=/tmp/tt-mpl .venv/bin/python -m eval.smoke_rallies` (external analysis
is disabled by the script; generated jobs and `eval/work/milestone2-smoke.json` are ignored).

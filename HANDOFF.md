# HANDOFF

Read this first, then `PROGRESS.md` (history, every measurement) and `AGENTS.md` (layout,
conventions). Last updated 2026-11-17 after Tasks 1a, 2 and 3 of the user's brief. Work is on
`main`; each change is its own commit. All metrics are development data (no held-out set).

## Current state

| Thing | Metric |
| --- | --- |
| Auto-Cut rally F1 (`eval.run --pose`, IoU >= .5) | coach_demo .500, match_b .629, 720p montage .722 |
| IMG_8782 Auto-Cut regression | 10/10 real rallies kept, 0/4 non-play kept |
| Identity audits, 12 frames each | IMG_8782 12 correct / 0 wrong / 0 abstained; match_b 8 / 0 / 4 |
| Coached stroke selection (8 peaks labelled from frames) | 5/5 real strokes kept, 3/3 post-point turns/walks rejected |
| Coach end to end | coaches the user on IMG_8782, coach_demo, both montage encodes (frame-checked) |
| Forehand/backhand auto-detection | fails its one labelled case (strict xfail); geometry candidate rejected |
| Tests | backend 342 pass, 2 network skips, 1 xfail; frontend 122 pass; build passes |

Samples (git-ignored `samples/`): `IMG_8782.MOV` (3:35 continuous match, phone far back),
`coach_demo.mp4` (640x360 drill), `match_b.mp4` (480p montage, 18 clips, crossfades),
`coaching-demo.mp4` (same montage at 720p; shares match_b's labels via `"also"`). The user is
the teal "CHINA" shirt, right-handed, 168 cm. OpenTTGames videos: ignored `data/openttgames/`
(~1.9 GB of the 10 GB cap).

## Done this session (user brief of 2026-11-17)

| Commit | Change | Measured |
| --- | --- | --- |
| 9f2299e | 1a: in an edited video every gap between candidates is scanned for crossfades (`floor_bounce.gaps_to_scan`, chunked `scan_joins`) | The 129.5-132.9 s rally was dropped as "another court" because its crossfade sat in a 4.0 s gap (only gaps <= 4 s were scanned). Now kept on both encodes; no other rally changed. F1 match_b .647 -> .629, 720p .743 -> .722, because it is detected from 131.4 s (IoU .41 with the 129.5 s label) |
| 8429cd6 | Ovtcharov forehand from the user's video `sQU95GWIR4Q` (0.4-8.4 s, cropped to the far player; `players.build --local`) | His two earlier forehands tracked his sparring partner and were dropped on Nov 15; a third cached clip tracked a commentator's webcam. New clip: visible 100%, 10 swings, right hand, skeleton on him |
| 2e6957e | 2: `players/compile.py` gives every match a card in rank order ("No forehand clip of X yet" when missing); cards moved to `frontend/app/jobs/[id]/matches.tsx`; `test/matches.test.ts`; demo re-run at the user's height (`MATCH_HEIGHT_CM = 168` in `scripts/refresh_demos.py`) | Demo video opened on "#2 MATCH": Ovtcharov ranked #1 with no forehand clip and was skipped. Cached JSON and a fresh API response had identical fields/order, so no rendering bug. New demo: Fan Zhendong 56%, Ma Long 55%, Harimoto 54%; video opens on #1 |
| 2bb8a6f | 3: `pipeline.real_strokes` (used by `key_moments` and the pose summary): peaks inside the rally (first-last hit +-0.15 s), within 0.15 s of a hit, in a playing stance (legs visible, knees < 170 deg); each rule relaxed only if nothing passes | Coach demo coached a turn away from the table after the point (57.86-58.12 s): the audio rally ran 1.5 s past the last stroke, and a bounce 0.04 s away made the turn the best-aligned peak |
| 1cb60b4 | 3: Coach demo regenerated at 2bb8a6f; page's how-it-works mentions real strokes only | Coaches the 56.26-56.76 s forehand loop (frame-checked); replay 55.0-57.71 s is all rally play |

Side effect to know: a pro profile with two clips takes the upper value as its "median" body
(`players/build._save`), so Ovtcharov's wide-stance forehand moved his stance to 2.17 and he
left this clip's top 3.

## Next steps (ordered)

1. **"Tap the player to analyze"** (user request, 2026-11-17). Proposed design, pending the
   user's approval:
   - A. `POST /players/detect` (FastAPI) and `/api/players/detect` (Next.js). Input: 4-8 JPEG
     frames the browser draws from the chosen file at times spread over the clip (no second
     upload of a large video), or `url` (backend downloads <=720p and samples). Per frame:
     `pose._pose_candidates` (existing torso and 1.5x body-span rules); per person an
     appearance (torso + legs colour histograms, body height ratio); cluster across frames.
     Returns `candidates[{id, time, box, thumb, seen, near}]`, `frame`, `suggested`,
     `decisive` (one candidate, or a clear appearance-vote winner). Tests: synthetic frames
     with 1 and 2 people; a phantom on a table is not a candidate.
   - B. Forms (Breakdown, Coach, Match): `PlayerPicker` ("Which one is you?": frame with
     tappable boxes plus thumbnails) only when `decisive` is false; job params `player_time`,
     `player_box` validated on both sides (`shared/limits.json`).
   - C. `pose.identity_from_box(video, time, box)` seeds the tracker from the selected person
     instead of `initial_identity`, in `run_video`, Coach `extract_pose` and `match_video`.
   - D. Tracker: appearance = torso + legs histograms + height ratio; cost = appearance +
     box IoU + motion, never near/far position; crop and upscale around the last box when the
     selected player is small or keypoints are weak.
   - E. Selected player visible < 40%: fail with "We lost the player you picked..." (no switch).
   - F. Result shows a thumbnail of who was analysed (`job.player.thumb`) and a "Change
     player" link that re-runs the job with the stored upload and a new selection.
   - Acceptance: 6-8 s two-player clips from IMG_8782 and the 720p coaching demo, each player
     selected in turn, skeleton checked on frames; cached demos unchanged; all tests pass.
2. **1b: learned forehand/backhand classifier.** Train a small model (logistic regression or
   gradient boosting on resampled wrist/elbow trajectories in the body frame) on OpenTTGames
   test_7 plus `train/` game strokes; freeze; score once on test_6/test_3 with the gates in
   `backend/eval/geometry_protocol.json` (selective precision >= .90, no wing recall drop
   > .05, hybrid accuracy improves, local backhand regression passes). Ship only if it passes;
   otherwise keep in `backend/eval/` and report. Stay under 10 GB of downloads.
3. **1c: block stroke type**, after 1b and measured the same way: `technique/strokes.py`,
   offline template in `technique/analyze.py`, `frontend/lib/strokes.ts`.

## Known bugs and open questions

- Late rally starts (the montage 129.5 s rally is detected from 131.4 s); quiet
  continuous-video rallies split (3 on coach_demo); one retrieval false rally on coach_demo.
- Same-camera hard cuts are not detected; relative figure size can then misfire.
- Real-stroke rules rest on 8 labelled peaks; the knee margin is thin (166 real vs 174 turn).
- An ambiguous montage whose first frame shows the partner nearest still seeds the partner
  (step 1 fixes this).
- A left-hander whose pooled bat colour stays under 1.8x gets "assumed right-handed" unless
  the request says otherwise.
- Contact-level hit precision/recall is unmeasurable without per-contact labels.
- The deep-agent Coach path (with `ANTHROPIC_API_KEY`) was not re-run; its tools share the code.

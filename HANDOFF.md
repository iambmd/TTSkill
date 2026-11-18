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
| Tests | backend 370 pass, 2 network skips, 1 xfail; frontend 145 pass; build passes |

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

1. **"Tap the player to analyze": done** (all six parts pushed):
   - A `dd3d502` detect endpoint (`technique/people.py`, `/players/detect`, browser frames or link).
   - C `e332896` jobs take `player_time` + `player_box`; `pose.identity_from_box` seeds tracking.
   - B `3d9be25` picker UI (`frontend/app/player-picker.tsx`, `VideoPicker findPlayer`).
   - D `7e1a55e` tracker: zoomed search around a small/missed player (`pose.zoom_regions`),
     torso decides + thigh veto, motion-predicted continuity. Far picks on 6 s clips: IMG_8782
     opponent 3% -> 18%, user far on the montage 28% -> 80%. Audits IMG_8782 12/0/0, match_b
     10/0/2 (8 s box corrected in `9a698f9`, frame-checked).
   - E `e74452a` "We lost the player you picked" when a pick is under 40% visible.
   - F `0ae5ec6` `job.player.thumb` + "Change player" (`/players/detect job=`, `POST /jobs/<id>/rerun`).
   Not verified here: the browser drawing frames from a local file (`drawFrames`) needs a real
   browser. Breakdown on the full IMG_8782 with the user picked and hand "auto" asks for the hand
   (pooled bat colour just under 1.8x); with the far opponent picked it completes (42% seen,
   skeleton on him).
   Picker hang, fixed 2026-11-18 (`a446a9e`, `8e20b2b`, `84cd05e`): the browser test saw detect
   take 178-301 s and pages stuck on "Finding the players". Detection is 1.5-3.5 s (timed per
   step); the dev backend was stuck in `--reload` restarts waiting for running work, and the
   frontend had no time limits (Chrome can't decode iPhone HEVC frames, so loadeddata/seeked
   never fired on Breakdown). Now: model reused per thread, 8 s detection budget, async endpoint
   in its own 2-thread pool cancelled on browser disconnect (checked direct and through
   Next.js), `make backend --timeout-graceful-shutdown 5`, 10 s/6 s frame-event limits, 30 s
   lookup limit, "Analyse anyway (auto-pick)" + "Try again". Browser check steps are in the
   commit `84cd05e` message and the session summary.
2. **1b: learned forehand/backhand classifier** (in progress). Cached pose windows: test_7 41
   contacts (calibration), test_6 31 + test_3 19 (validation, frozen). Too few to train on, so
   add test_1 (84 strokes), test_4 (71), test_5 (27): download, verify each side's hitting hand
   on frames (labels give table side, not hand), `eval/extract_strokes.py`, delete the raw video.
   Train a small model (logistic regression with an abstain threshold) on calibration only;
   freeze; score once on test_6/test_3 against `eval/geometry_protocol.json`'s gates.
   State on 2026-11-17: raw test_2/3/6/7 videos deleted (pose windows for 3/6/7 stay cached in
   `backend/eval/work/accuracy-next/`). `data/openttgames/test_5.mp4` (720 MB) is downloaded, not
   yet extracted. Its left (orange) player looks right-handed (watch on the arm hanging at his
   side; confirm), the right (dark shirt) player is unverified. test_1 is 1.05 GB, test_4 2.25 GB.
   No scikit-learn in the venv: write the logistic regression in numpy rather than add it.
3. **1c: block stroke type**, after 1b and measured the same way: `technique/strokes.py`,
   offline template in `technique/analyze.py`, `frontend/lib/strokes.ts`.

## Known bugs and open questions

- Late rally starts (the montage 129.5 s rally is detected from 131.4 s); quiet
  continuous-video rallies split (3 on coach_demo); one retrieval false rally on coach_demo.
- Same-camera hard cuts are not detected; relative figure size can then misfire.
- Real-stroke rules rest on 8 labelled peaks; the knee margin is thin (166 real vs 174 turn).
- An ambiguous montage whose first frame shows the partner nearest still seeds the partner
  when no pick is made; the picker asks in that case.
- A left-hander whose pooled bat colour stays under 1.8x gets "assumed right-handed" unless
  the request says otherwise.
- Contact-level hit precision/recall is unmeasurable without per-contact labels.
- Running `npm run build` while `next dev` runs breaks the dev server (shared `frontend/.next`);
  build in a separate worktree.
- The deep-agent Coach path (with `ANTHROPIC_API_KEY`) was not re-run; its tools share the code.

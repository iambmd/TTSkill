# HANDOFF

Read this first, then `PROGRESS.md` (history, goal table, every measurement) and `AGENTS.md`
(layout, conventions). Last updated 2026-11-17 after the player-selection and Coach-hand fixes.
Work is on `main`; each change is its own commit. Scope set by the user: accuracy fixes only;
the Milestone 3 product feature is deferred.

## Current state (development data only; no held-out set exists)

| Thing | Metric |
| --- | --- |
| Auto-Cut rally F1 (`eval.run --pose`, IoU >= .5) | coach_demo .500, match_b .647, 720p montage .743 |
| IMG_8782 Auto-Cut regression | 10/10 real rallies kept, 0/4 non-play kept |
| Identity audits, 12 frames each | IMG_8782 12 correct / 0 wrong / 0 abstained; match_b 8 / 0 / 4 |
| Coach end to end | coaches the user on IMG_8782, coach_demo, both montage encodes (frame-checked); hand from pooled bat colour on IMG_8782 and coach_demo |
| Forehand/backhand auto-detection | fails its one labelled case (strict xfail); geometry candidate rejected |
| Tests | backend 336 pass, 2 network skips, 1 xfail; frontend 119 pass, build passes |

Samples (git-ignored `samples/`): `IMG_8782.MOV` (3:35 continuous match, phone far back),
`coach_demo.mp4` (640x360 continuous drill), `match_b.mp4` (480p montage, 18 clips with
crossfades), `coaching-demo.mp4` (the same montage at 720p; shares match_b's labels via
`"also"`). The user is the teal "CHINA" shirt, right-handed. OpenTTGames calibration and
validation videos are in ignored `data/openttgames/` (about 1.9 GB of the 10 GB cap).

## This session

| Commit | Change | Why |
| --- | --- | --- |
| a49f107 | `technique/pose.py:initial_identity` seeds the player from 24 frames across the video (`identity.dominant_appearance`), falling back to the first frame's nearest person when the vote is ambiguous (`identity.choose_seed`); `implausible()` rejects bodies under 1.5 torso lengths tall | IMG_8782 seeded the opponent. Codex's draft raised on a 7 v 7 tie on the 720p coaching demo, and the fallback frame held a table phantom |
| fd4598c | `pose.bat_side(assume=...)`; Coach reads the hand from the request (`coach.hand_from_request`), states "assumed right-handed" otherwise, and reuses one hand decision in render and match (`tools.Session.hand`) | Coach on IMG_8782 failed with "couldn't tell your hitting hand" and has no hand field |
| f16f93f | `eval/geometry.py`, `extract_strokes.py`, `score_geometry.py`, `geometry_protocol.json` | Codex's frozen wing experiment; failed validation, kept reproducible, not in production |
| ed8dade | `choose_window` sums bat colour over its six scans (`win["paddle"]`); `bat_side(pooled=...)` uses it after the window's cues and a stated hand, before the faster wrist | IMG_8782 hand was assumed; pooled colour named the true hand on 8/8 videos (4 samples + mirrored copies), 6/8 decided at the unchanged 1.8x rule, none wrong |
| db54937 | Coach chooses the window and seed once (`Session.window/identity`); `run_video`/`match_video` take `chosen`, `identity` | Each step rescanned; Coach 111 -> 88 s (coach_demo), 220 -> 170 s (IMG_8782) |

Task 1a (2026-11-17): the 129.5-132.9 s montage rally was dropped as "another court"
because the crossfade before it (129.1 s) sat in a 4.0 s gap, and gaps were only scanned up
to 4 s; it joined the previous gym's clip, where the near player is bigger. In an edited
video every gap is now scanned (`floor_bounce.gaps_to_scan`, chunked `scan_joins`). Only that
rally changed on both encodes (also found a missed join at 67.8 s); coach_demo/IMG_8782 have
no joins. F1 match_b .647 -> .629, 720p .743 -> .722: the rally is real but detected from
131.4 s (label 129.5 s), IoU .41, so it scores as an unmatched detection. Late starts are open.

Task 2 (2026-11-17): the pro-match demo video opened on "#2 MATCH". No rendering bug: the
cached JSON and a fresh API response have the same fields and order. Cause: Ovtcharov ranked
#1 with no usable forehand clip (both tracked his sparring partner and were dropped on Nov 15),
and `players/compile.py` silently skipped pros without a clip. Now every match gets a card in
rank order ("No forehand clip of X yet" when missing); the cards component moved to
`frontend/app/jobs/[id]/matches.tsx` and says the same; `frontend/test/matches.test.ts`
checks the top match renders first. Ovtcharov's forehand added from the user's video
`sQU95GWIR4Q` (0.4-8.4 s, cropped to the far player; commit 8429cd6). His profile's stance
is now the upper median of his two clips (2.17), so he no longer makes this clip's top 3.
Demo re-run with the user's real height (168 cm, `MATCH_HEIGHT_CM` in `scripts/refresh_demos.py`):
Fan Zhendong 56%, Ma Long 55%, Harimoto 54%, each with a clip; the video opens on #1.

Decisions: an ambiguous seed vote falls back rather than failing (failing killed Coach on
the main demo video). Breakdown and Match still ask for the hand (their forms can). A
left-hander who doesn't say so gets a mirrored analysis; the reply tells them how to fix it.

## Next steps (ordered, each implementable directly)

1. **Forehand/backhand.** The hand-built geometry failed (see PROGRESS.md). Next candidate:
   a small learned classifier (logistic regression or gradient boosting on resampled
   wrist/elbow trajectories in the body frame) trained on OpenTTGames test_7 plus the
   `train/` games' strokes, frozen, then scored once on test_6/test_3 with the same gates
   as `geometry_protocol.json`. Download only the strokes' videos needed; stay under 10 GB.
   Do not enable in production unless it passes the gates and the local backhand regression.
2. **Block stroke type** after step 1: `technique/strokes.py` (label, direction, phases,
   focus), offline template in `technique/analyze.py`, `frontend/lib/strokes.ts`.

## Known bugs and open questions

- Quiet continuous-video rallies still split (3 on coach_demo); one retrieval false rally remains.
- Late rally starts: the montage 129.5 s rally is detected from 131.4 s (IoU .41).
- Same-camera hard cuts are not detected; relative figure size can then misfire.
- On an ambiguous montage whose first frame shows the partner nearest, the fallback seed
  coaches the partner. A "tap yourself" override in the UI would remove this.
- A left-hander whose pooled bat colour stays under 1.8x (2 of the 4 mirrored test videos)
  gets "assumed right-handed" unless the request says otherwise; the reply says how to fix it.
- Contact-level hit precision/recall is unmeasurable without per-contact labels.
- A profile with two clips takes the upper of the two values as its "median" body (`players/build._save`), so one wide-stance clip moves a pro's stance.
- The deep-agent path (with `ANTHROPIC_API_KEY`) was not re-run this session; the fallback
  plan was. Its tools share the same code.

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

Decisions: an ambiguous seed vote falls back rather than failing (failing killed Coach on
the main demo video). Breakdown and Match still ask for the hand (their forms can). A
left-hander who doesn't say so gets a mirrored analysis; the reply tells them how to fix it.

## Next steps (ordered, each implementable directly)

1. **Montage rally rejected as "another court"** (129.5-132.9 s): print `refine()`'s joins
   and per-rally `figure_size` around 120-138 s on both encodes. If the clip has one rally,
   `other_court` should not run; if a join was missed, scan gaps up to `MERGE_GAP` for joins
   even when the gap is under `2 * JOIN_MARGIN`. Acceptance: F1 on both montage encodes does
   not drop; coach_demo keeps rejecting its three neighbouring-court rallies.
2. **Forehand/backhand.** The hand-built geometry failed (see PROGRESS.md). Next candidate:
   a small learned classifier (logistic regression or gradient boosting on resampled
   wrist/elbow trajectories in the body frame) trained on OpenTTGames test_7 plus the
   `train/` games' strokes, frozen, then scored once on test_6/test_3 with the same gates
   as `geometry_protocol.json`. Download only the strokes' videos needed; stay under 10 GB.
   Do not enable in production unless it passes the gates and the local backhand regression.
3. **Block stroke type** after step 2: `technique/strokes.py` (label, direction, phases,
   focus), offline template in `technique/analyze.py`, `frontend/lib/strokes.ts`.

## Known bugs and open questions

- Quiet continuous-video rallies still split (3 on coach_demo); one retrieval false rally remains.
- Same-camera hard cuts are not detected; relative figure size can then misfire.
- On an ambiguous montage whose first frame shows the partner nearest, the fallback seed
  coaches the partner. A "tap yourself" override in the UI would remove this.
- A left-hander whose pooled bat colour stays under 1.8x (2 of the 4 mirrored test videos)
  gets "assumed right-handed" unless the request says otherwise; the reply says how to fix it.
- Contact-level hit precision/recall is unmeasurable without per-contact labels.
- The deep-agent path (with `ANTHROPIC_API_KEY`) was not re-run this session; the fallback
  plan was. Its tools share the same code.

# HANDOFF

Read this first, then `PROGRESS.md` (history and goal table) and `AGENTS.md` (layout, conventions).
Last updated 2026-11-17 after Milestone 2 (clip-aware rally refinement). Work is on `main`; code and evaluation/report changes are separate commits.

## Current state (measured, development data only)

| Thing | Metric |
| --- | --- |
| Auto-Cut rally F1 (`eval.run --pose`, IoU >= .5) | coach_demo .500, match_b .647, 720p montage .743 |
| Measured merges / splits | coach_demo 0 / 3; match_b 0 / 1; 720p montage 0 / 1 |
| IMG_8782 Auto-Cut regression | 10/10 real rallies kept, 0/4 non-play kept |
| Identity audit, match_b, 12 frames | 8 correct, 0 wrong, 4 abstained |
| Coach end to end | breakdown produced on 4/4 test runs |
| Forehand/backhand auto-detection | fails its one labelled case (strict xfail) |
| Tests | backend 321 pass, 2 network skips, 1 known backhand xfail; frontend 119 pass and production build passes |

Samples (git-ignored `samples/`): `IMG_8782.MOV` (3:35 continuous match), `coach_demo.mp4`
(640x360 continuous drill), `match_b.mp4` (480p montage, 18 clips), `coaching-demo.mp4`
(the same montage at 720p). The user is the teal "CHINA" shirt, right-handed.

## Upgrade plan (Milestone 1)

Three weakest points, each with the evidence, the options compared, and the choice.

### 1. Rally segmentation uses audio gaps only (Auto-Cut F1 .45 / .34)

Where F1 is lost (per-rally breakdown of `eval.run`):
- coach_demo: 4 of 11 real rallies are split into 2-3 pieces by quiet stretches; 4 false
  rallies (1 ball retrieval, 3 at the end when the table is empty and a neighbouring court plays).
- match_b: detections straddle montage joins; late starts; 2 quiet rallies missed.

| Option | Evidence | Cost | Verdict |
| --- | --- | --- | --- |
| Tune threshold/gap/min_hits | best of 80 settings: mean F1 .39 -> .50, fitted to 2 clips | minutes | rejected |
| Per-onset audio classifier | within-video AUC of every feature .54-.68; the ball sounds the same in and out of play | days + contact labels | rejected |
| Pose evidence in the quiet gap | swing .2-.9 and 1-4 weak onsets/s in both same-rally and different-rally gaps | - | rejected |
| **Clip structure from video** | crossfade score: 16 peaks on the montage (14 at labelled clip gaps), none >= .35 on continuous video; prototype F1 .32 -> .63 (480p) / .69 (720p) | reuses frames the pose filter decodes | **chosen (Milestone 2)** |
| Ball tracking (TTNet/WASB-style) | highest ceiling; fixes continuous-video splits | GPU, labelled amateur footage, weeks | long term |

Chosen design: (a) crossfade joins = share of changed pixels that ramp linearly over 0.6 s;
(b) split candidates at joins; (c) in a video with joins, merge pieces of one clip when the
gap is <= 4 s; (d) drop a rally whose biggest figure is under 80% of the clip's usual
near-player size (another court). Not fixed by this: splits inside continuous recordings.

### 2. Forehand/backhand is read at contact, on an axis that flips in side views

Evidence: on the two labelled strokes the shoulder-axis feature scores both 1.4-1.7 (bat side).
The wrist's position along the direction of play during the backswing separates them:
forehand -0.9..-1.0 torso lengths (behind the hips), backhand +0.7..+0.9 (in front).
There is no block type. Nothing local is labelled, but `data/openttgames/extended/` has
~1,700 strokes labelled `{table side}_{forehand|backhand}_{loop|push|block|flick|serve}`
on side-on video (frame-indexed JSON; videos download per file from lab.osai.ai).

| Option | Verdict |
| --- | --- |
| DTW templates from OpenTTGames (Codex) | failed transfer: 1 abstain, 1 wrong of 2 |
| **Per-stroke geometric features, self-calibrated per video** | **chosen**; spec in Milestone 4 |
| Claude vision on 3-5 frames per contact | optional labeller when a key is set; costs per stroke |

### 3. The coached player is seeded from the first five frames

Evidence: on IMG_8782 the user walks in at ~1 s, so the seed is the far opponent (hip x .49,
height .31) and the tracker then follows the opponent in 61% of mid-rally frames. Coach on
the user's own match would coach the wrong person. The matcher itself is sound (0 wrong on the audit).

| Option | Verdict |
| --- | --- |
| **Seed = the person nearest the camera most often across ~24 frames spread over the video** (cluster the largest person's torso histograms, take the biggest cluster's medoid) | **chosen**; cheap, no UI |
| Let the user tap themselves on a frame | good override, needs UI; later |
| Re-ID embedding model (OSNet) | new dependency and weights; not needed yet |

## Milestone 2 completed

Production commit: `94996b7`. Continued the existing uncommitted `app/clips.py` and
`floor_bounce.py` draft. Auto-Cut
and Coach now split candidates at crossfades, regroup pieces within a clip, and clamp
cut padding at the joins. The 720p 27.45–50.15 s four-rally merge is fixed. A relative
figure-size check removes three neighboring-court false rallies on coach_demo.

Two important corrections to the draft: non-play candidates must block regrouping
(otherwise retrieval at 114–117 s bridges the 107–112 and 121–127 s rallies); and
unsampled gaps must not contribute a fast-wrist vote. The first merge-before-filter
attempt was measured and rejected. Final P/R/F1, the failed attempt, exact reproduction
commands and remaining cases are in `backend/eval/README.md`, under Milestone 2.

`eval.run --baseline` now loads revision-local sibling modules with a real `__file__`.
Both montage encodes use the same labels/timeline; they are not independent examples.
Raw videos and JSON reports stay ignored, and no new dataset downloads were needed.
The site refresh requested earlier is complete and is not the next task.

## Next steps

1. Milestone 3 was described only as “one product feature”; no feature or acceptance
   criteria were left in this handoff. Get that brief before choosing a new product feature.
2. Milestone 4: specify and validate the per-video stroke geometry and majority-near-player
   seeding described above. Automatic backhand recognition and IMG_8782 identity remain open.
3. Rally follow-up: hard-cut boundaries, quiet continuous-play splits, and independently
   labelled contacts/held-out clips. Do not report the current tuning clips as held-out.

## Known bugs and open questions

- Coach on IMG_8782 tracks the opponent (weakness 3).
- Hard cuts (no crossfade) between clips from the same camera are not detected. An undetected
  camera/view change also makes relative figure size unreliable: the 129.5–132.9 s montage
  rally is currently rejected as “another court.”
- Coach runs the window scan twice (pose tool, then render): about a minute per job.
- Quiet continuous-video rallies still split; one retrieval false rally remains on coach_demo.
- Contact-level hit precision/recall is still blocked by missing contact labels. The unchanged
  play-window proxy precisions are .699 / .876 / .874 (coach_demo / 480p / 720p).
- All metrics are on clips that also informed the thresholds. No held-out set exists.

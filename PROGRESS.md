# Progress: detection and coaching accuracy

Last updated 2026-11-17. Covers the original fixes, Milestone 2, and the accuracy
continuation below. Local sample results are **development data, not held-out**.
The final section separately records two reserved visual validation clips; that
stroke experiment failed its promotion criteria and is not in production.

## Status by goal

| Goal | Status | Evidence |
| --- | --- | --- |
| a. Floor bounces / shoe squeaks not counted as hits | partial | The pre-serve floor-bounce routine in IMG_8782 (14.4–19.8 s) is dropped by the crouch check (`tests/test_floor_bounce.py`). Within a kept rally, audio still counts every sharp sound: the onset play-window proxy is unchanged (coach_demo .699, match_b .876). Contact-level hit precision/recall needs per-contact labels, which don't exist. |
| b. Merged rallies split; serve prep not counted | partial | merges = 0 on both labelled clips; anchored grouping keeps weak sounds from bridging breaks (`tests/test_rally.py`). Pre-serve span 120.0–122.9 s in IMG_8782 is dropped. Milestone 2 splits the 720p 27.4–50.1 s merge at crossfades; measured merges are now zero on both encodes. Quiet continuous-video splits remain. |
| c. Correct hitting hand + stroke type | partial | Hand: Coach states an assumption (right) when no cue is decisive, as on IMG_8782, and reads "left-handed" from the request. Otherwise right on every run (bat colour on the coaching demo and the match example; faster-wrist fallback on coach_demo), matching the provisional label. No per-contact hand labels. Forehand/backhand auto-detection still fails on the one labelled backhand (strict xfail). There is no **block** stroke type, and no subtype (drive/topspin/push/flick) accuracy can be measured. |
| d. Coaching tracks you, not your opponent | done on the available evidence | Video-wide near-player seeding fixes the IMG_8782 audit: 2 correct / 5 wrong / 5 abstained → **12 correct / 0 wrong / 0 abstained**. match_b stays **8 / 0 / 4**. Coach completes on IMG_8782 and the 720p coaching demo, coaching the user in both (checked on frames). Coach, Breakdown and Match share this selector. Sparse development audits do not establish full-video accuracy; an ambiguous vote falls back to the first frame's nearest person. |
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

## Accuracy continuation (2026-11-17)

User scope: accuracy fixes only; Milestone 3's new product feature is deferred.

1. **Player selection:** compare first-frame-seed baseline tracks with a dominant
   near-player appearance from 24 samples across each clip, retaining a fixed identity.
2. **Stroke geometry:** validate the proposed backswing/direction-of-play features
   on labelled contacts before enabling them in production. Separate calibration
   footage from validation footage; do not tune on validation results.
3. **Verification:** run relevant regressions, full backend checks, frontend build,
   and update this file and HANDOFF with actual outcomes before separate commits/push.

Official OpenTTGames and Extended OpenTTGames access/license pages were rechecked
on November 17: both state CC BY-NC-SA 4.0. Existing annotations are local; no new
video had been downloaded at the start of this continuation. Subsequent downloads
and results are recorded below; footage stays local and counts toward the 10 GB limit.

### Player-selection trial and data check

The initial video-wide seed trial on IMG_8782 changes the 12-frame manual audit
from **2 correct / 5 wrong / 5 abstained** to **12 correct / 0 wrong / 0 abstained**;
sampled track visibility rises .617 → .952. Labels are in
`eval/regressions/img8782_identity.json`. This is a development audit, not full-video
identity accuracy. The same trial abstains on match_b's tied appearance-cluster
vote, so it is **not ready to ship**; montage compatibility is being investigated.

Downloaded `test_2.mp4` (225,118,372 bytes, calibration) and `test_3.mp4`
(487,941,402 bytes, reserved validation) after checking public access and terms.
New total: **713,059,774 bytes**, well below the 10 GB cap including the documented
previous downloads. Hashes, URLs and splits are in ignored
`data/openttgames/accuracy_downloads.json`. These videos are for visual timing/wing
evaluation, not audio training; no raw footage or generated features will enter Git.

### Revised selector and stroke sample coverage

The montage's two leading clusters had **7 vs 6** observations, not an exact tie.
The initial extra two-vote margin rejected the correct largest cluster. Following
the handoff's largest-cluster design, the selector now rejects exact ties and weak
support, while keeping the existing strict appearance-distance threshold. Re-audit:
match_b remains **8 correct / 0 wrong / 4 abstained**; IMG_8782 remains **12 / 0 / 0**.
Shipped in `a49f107` after the checks below.

Annotation counts showed test_2 has only forehands, so it cannot calibrate both
wings. Added test_7 (41 non-serve/non-lob contacts, calibration) and test_6 (31,
reserved validation), while test_3 has 19 validation contacts including a left-hander.
Total new video downloads are now **1,877,170,209 bytes**; all remain ignored and
within the 10 GB limit. The simple “wrist in front = backhand” rule already fails
forehand pushes on calibration, so it will not ship unchanged. Evaluating calibrated
forward/lateral backswing geometry before opening validation results.

### Geometry candidate frozen before validation

On the 41 test_7 calibration contacts, the existing wing decision gets **16/41**
correct. The candidate supplies a decision on **22/41** contacts, of which **21**
are correct; falling back to the existing decision elsewhere gives **32/41**.
It also returns backhand on the local 43.3 s regression and forehand on the prior
62.8 s development check. These are calibration observations, not validation.

The candidate and promotion criteria are frozen in ignored
`eval/work/accuracy-next/geometry-freeze.json` before scoring test_6/test_3:
selective precision >= .90, improved hybrid accuracy, no wing's recall falling
more than .05, and the real backhand regression passing. If it fails, retain it
as an experiment rather than retuning on those validation results.

### Frozen validation outcome — candidate rejected

The geometry candidate failed its predeclared promotion gates. On test_6, wing-stage
correctness rises **17/31 → 20/31**, but selective precision is **16/21 (.762)** and
forehand recall falls **1.000 → .857**. On test_3 it falls **14/19 → 13/19**, with
backhand recall **.286 → .143**. Combined, only **25/31 (.806)** supplied decisions
are correct. These are visual, labelled-contact/player/hand-conditioned results,
not end-to-end stroke or audio accuracy. No thresholds were changed after validation.
The candidate stays in `backend/eval/` (committed as `f16f93f`); production stroke
detection is unchanged and the automatic-backhand regression remains an expected failure.

### Player selection and Coach hand shipped (a49f107, fd4598c)

Verifying the video-wide seed end to end found two problems, both fixed before committing:

- **Ambiguous vote failed Coach on the user's 720p coaching demo.** The user's cluster and a
  mixed cluster (partner frames, two user frames, crossfades) tied 7 v 7, and the draft
  raised "couldn't choose a consistent player". An ambiguous vote now falls back to the
  nearest person in the first sampled frame, the previous default.
- **That first frame held a phantom.** MediaPipe placed a skeleton on the table base with
  full visibility and a longer torso than the player's, but a body only 0.87 torso lengths
  tall. `implausible()` now requires a body at least 1.5 torso lengths tall.
- **Coach then failed on IMG_8782 with "couldn't tell your hitting hand".** Seen from
  behind at a distance, no cue was decisive in the chosen window (bat colour 1.5x, under
  the 1.8x bar), and Coach has no hand field. Coach now reads the hand from the request
  ("left-handed", "lefty") and otherwise states "I assumed right-handed" in its reply.
  Breakdown and Match still ask, since their forms have a hand selector. Across the six
  candidate windows, bat colour said right in all six (the truth); wrist speed at contacts
  decided once, wrongly (left); the faster wrist split 3/2/1.

| Check | Before | After |
| --- | --- | --- |
| IMG_8782 identity audit (12 frames) | 2 correct / 5 wrong / 5 abstained | 12 / 0 / 0 |
| match_b identity audit (12 frames) | 8 / 0 / 4 | 8 / 0 / 4 |
| Coach on IMG_8782 ("best rallies and coach my technique") | no breakdown | 5-rally reel + forehand drive breakdown of the user, 80.6-88.1 s, assumed right-handed |
| Coach on the 720p coaching demo | user, 54-60 s | same (hips x .14, right hand by bat colour) |

Backend: **335 passed, 2 network skips, 1 known automatic-backhand xfail** (with
`TTSKILL_SAMPLE` = IMG_8782). The seed is chosen on all demo inputs and samples.

### Bat hand pooled across rallies; Coach scans once (ed8dade and the following commit)

The bat hand was decided from one 8 s window. `choose_window` already scans the six busiest
rallies with the player's identity; it now sums bat colour over them, and `bat_side` uses that
before falling back to the faster wrist or a stated assumption. On 8 videos (IMG_8782,
coach_demo, both montage encodes, and mirrored copies that look left-handed) pooled colour
named the true hand every time (ratios 1.72-2.86); at the unchanged 1.8x rule 6/8 decide and
none is wrong. Coach on IMG_8782 now reports right by bat colour instead of an assumption.

Coach also chose its window three times (pose, render, pro match). It now chooses once:
coach_demo 111 -> 88 s, IMG_8782 with rallies 220 -> 170 s, same window, hand and stroke.
Backend: **336 passed, 2 network skips, 1 known xfail**.

## Coach visual restyle (2026-11-20)

- Restyled the Coach form and Coach job view with a court-marked upload target, ball orange, existing Barlow fonts, and light and dark training tokens in the global stylesheet. The Coach stylesheet scopes their use to this feature. See [the style guide](docs/STYLE.md).
- Coaching notes and videos occupy separate shrinkable grid rows. The result still uses the existing plan disclosure and native video controls.
- Compared the generated concept with the Playwright render for headline hierarchy, palette, form columns, upload framing, notes separation, and native media controls. The implementation keeps the existing copy, navigation, and real demo footage. One visual correction narrowed an accent selector that had turned the whole upload target orange and gave the mobile link field more space above the submit bar.
- Playwright Chromium ran against the local demo-mode dev server at 390 and 1440 px. Both widths passed the upload-to-demo-result flow, plan disclosure, video playback and seek, and geometry checks for horizontal overflow and notes/video overlap. The theme toggle and light surfaces were checked at 1440 px. [Mobile](docs/screenshots/coach/dark-390.png) · [Desktop](docs/screenshots/coach/dark-1440.png)
- Frontend tests passed (172). ESLint with a temporary Next.js configuration reported zero errors and five existing image warnings. The repository's lint script prompts for first-time configuration.
- The Next.js production build passed.

## Coach polish (2026-11-20)

- Below 600 px, Coach puts its navigation in a full-width scrollable row beneath the brand and theme toggle. All six tabs fit at 390 px. The shared header divider is the single line above Coach.
- The disabled submit button uses faded orange and shows “Add a video or link to start” while the form is blocked. The existing submit conditions still control when the button is enabled.
- Playwright checked both widths for clipping, the disabled hint, demo submission, and notes/video separation. Updated the [390 px](docs/screenshots/coach/dark-390.png) and [1440 px](docs/screenshots/coach/dark-1440.png) dark screenshots.
- Committed the Next.js ESLint configuration and locked its development dependencies. `npm run lint` completed without prompting with zero errors and five existing image warnings. All 172 frontend tests passed.
- The Next.js production build passed.

## Coach table and rubber palette (2026-11-20)

- Coach uses near-black and table blue in dark mode, lavender-tinted surfaces in light mode, and rubber red for primary controls. Orange marks the brand ball and the video-link preview. The [style guide](docs/STYLE.md) records both palettes and the forehand, backhand, and improvement tokens.
- Playwright checked the form and demo result at 390 and 1440 px in each theme. All six tabs fit at 390 px. The header has one divider, the disabled hint appears below the button, and notes and video stay in separate rows. Retook all four screenshots in [the Coach screenshot folder](docs/screenshots/coach).
- Rendered text, placeholder, input-boundary, and keyboard-focus contrast checks passed the applicable WCAG AA thresholds. The lowest sampled small-text contrast was 4.89:1 in dark and 4.96:1 in light.
- All 172 frontend tests passed. The committed ESLint config ran without prompting and reported five existing image warnings.
- The Next.js production build passed.

## Site-wide Coach style rollout (2026-11-20)

- Shared foundation. Extracted the site header and published the Coach form, surface, upload, field, button, and media styles for reuse. Disabled primary buttons have an outlined red treatment with muted text in both themes. The Coach form keeps its layout and disabled hint. All 172 frontend tests passed.
- Home. Matched the Coach title, media frame, cards, section labels, and demo links while keeping the hero video and its playback control. All 172 frontend tests passed.
- Breakdown. Adopted the shared upload, two-column form, before/after layout, and result frame. Forehand and backhand labels use their documented colors. All 172 frontend tests passed.

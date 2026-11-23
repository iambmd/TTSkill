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
- Pro Match. Reused the shared form, upload and comparison frames, and matched the height toggle and pro result cards to the palette. All 172 frontend tests passed.
- Auto-Cut. Paired the shared upload box with the existing mode, rally controls, and detection settings. The layout keeps those settings readable on phones. All 172 frontend tests passed.
- Gear. Restyled both Rubber Finder and Pro Setups. Recommendations and searchable setups use the shared panels, and grip-side labels use rubber red and charcoal. All 172 frontend tests passed.
- Site-wide verification. Playwright exercised demo submission and results, Home playback, Gear budget and search, and the Coach light theme. All six tabs fit at 390 px. Added mobile scroll clearance for the sticky header and submit bar and verified a focused field was reachable at 390 × 844. The screenshot folder has both dark widths for all seven routes and both light widths for Coach. Playwright blocked external images so the Pro Setups screenshots show the built-in fallbacks.
- Final checks. All 172 frontend tests passed again, lint completed with five existing image warnings, and the production build passed. No new dependencies were added.

## Upload-first match flow (2026-11-22)

1. Home now starts a highlight job when you select or drop an MP4/MOV. Auto-Cut results link to Coach and Breakdown with the stored upload. The Auto-Cut form and results use player-facing copy and keep algorithm settings out of the UI. Build, lint, all 172 frontend tests, and both backend upload-reuse cases passed.
2. Auto-Cut reports extraction, rally review counts, ranking, and render progress. Waiting shows a duration-based ETA and the first playable clip while the reel renders. The job URL resumes polling after refresh, and navigation cancels the active request. Build, lint, all 172 frontend tests, and 23 Auto-Cut backend cases passed.
3. Results now publish thumbnail cards, ranked clips, individual downloads, and an ordered export of the current selection. Full-match cuts still merge overlaps in the original reel and keep individual rally clips for editing. The Coach and Breakdown forms accept a rally reference and analyze its saved time range. Build, lint, 173 frontend tests, and 26 targeted backend cases passed.
4. Home now checks backend health and offers a retry. Upload errors keep the file available for retry, failed polls stop until retried, and no-rally results give filming tips. The job UI uses player-facing errors. Build, lint, 175 frontend tests, 28 targeted backend cases, and a 375 px Playwright flow passed.
5. Added a skip link, kept keyboard focus on rally controls after reordering and removal, and announced progress and completion in live regions. The existing demos have visible descriptions associated with their players. Reduced motion suppresses decorative effects, and videos start on request. Build, lint, and all 175 frontend tests passed. Playwright passed at 375 px in both themes, including keyboard upload, rally editing, and the four cached demo results. Sampled normal text reached at least 4.89:1 in dark mode and 4.64:1 in light mode. The sampled large text, input boundaries, and focus indicators also met their [WCAG 2.2 AA contrast thresholds](https://www.w3.org/TR/WCAG22/#contrast-minimum).

The production frontend and a local FastAPI instance processed the existing match example from Home at 375 px. Playwright observed a ranged first-clip preview before completion, checked the rally thumbnail and clip, downloaded a reordered export, and confirmed that Coach showed the selected time range and Breakdown reused the full match. The full FastAPI endpoint test file finished with 130 passes and one opt-in YouTube test skipped.

## US rubber purchase links (2026-11-22)

The catalog has 320 verified links and 90 Megaspin links marked unverified. Verified coverage rose from 165 to 244 of the 984 Rubber Finder entries after reviewing 100 entries that started without a verified link.

| Rubber Finder scope | Verified | Remaining gaps |
| --- | ---: | --- |
| This round’s 100 priority entries | 79 | 16 with a Megaspin candidate only and 5 with no confirmed US listing |
| All 984 ratings entries | 244 | 740 without a verified link, down from 819 |
| Previous high-priority entries | Existing Butterfly US, Paddle Palace, DHS Sports USA and JOOLA USA links plus additional Amazon links | Butterfly US Tenergy 64 still needs a title check. The two pro Hurricane 3 blue-sponge labels specifying 40° or 40.5° and 2.1 mm, the pro Hurricane 8 orange 37° and 2.1 mm, and Tibhar K3 Pro Special still lack exact verified matches. |

The ten requested brands ranked first. Within that group and among the remaining brands, the audit used Megaspin’s popularity order where available, then exact listings at specialist stores and the catalog’s user ratings as tie-breakers. Current retailer and manufacturer listings provided a check against discontinued models. The audit skipped discontinued listings such as Butterfly Spin Art, Yasaka Rising Dragon, and DHS PF4-50. [Megaspin popularity order](https://www.megaspin.net/store/default.asp?brand=All&cid=rubbers&sort=popularity) · [Tibhar current rubber range](https://tibhar.info/en/product-category/rubbers/) · [Donic current rubber range](https://www.donic.com/belaege/)

The trusted Butterfly Rubber tab listed 22 exact ASINs, including Roundell Soft. The JOOLA and STIGA storefronts showed rackets and accessories in the tabs checked. The audit found 20 exact Amazon other-seller listings with visible US offer prices that passed the threshold. Buy menus label them “Amazon (other seller)” and put them last even when an affiliate tag is configured. [Butterfly Rubber tab](https://www.amazon.com/stores/page/4325729E-0DDF-4FA8-A737-27BCC08A2070) · [JOOLA storefront](https://www.amazon.com/stores/JOOLANorthAmerica/page/54862E6E-D0CD-466E-BBDD-72DB8E617060) · [STIGA storefront](https://www.amazon.com/stores/STIGA/page/BC1F59CB-CE5D-44D6-BFC1-F7EF88B33AE4)

The checker retried Megaspin product URLs using a desktop Chrome User-Agent with a 2.5-second delay between requests. The manual review links below still returned HTTP 403. The app labels these links “unverified” and shows “Not sold in the US yet” where the catalog has no US source.

### Rejected Amazon offers

These exact offers were excluded by the price screen. The amounts are recorded here for the audit.

| Rubber | ASIN | Amazon offer vs. catalog reference |
| --- | --- | --- |
| DHS Hurricane 9 Pink | B0HR6G223Q | $14.95 vs. $38.00 |
| DHS NEO Hurricane 3 Provincial (Blue Sponge) | B07TMG97NG | $66.95 vs. $100.00 |
| DHS NEO Hurricane 3 Provincial (Blue Sponge) | B0HHMZ4YN2 | $52.22 vs. $100.00 |

<details>
<summary>Ranked audit of 100 entries and Megaspin manual review links</summary>

| Rank | Rubber | Verified US sources | Megaspin manual review |
| ---: | --- | --- | --- |
| 1 | Xiom Vega Pro | Go Table Tennis, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-pro) |
| 2 | Xiom Vega Europe | Go Table Tennis, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-europe) |
| 3 | Xiom Omega IV Pro | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-iv-pro) |
| 4 | Butterfly Tackiness Chop 2 | Paddle Palace | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-tack-chop-ii) |
| 5 | Nittaku Hurricane Pro III Turbo Blue | Paddle Palace, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=n-h3-pro-t-b) |
| 6 | Andro Rasanter V42 | Go Table Tennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=andro-rasanter-v42) |
| 7 | Andro Rasanter V47 | Go Table Tennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=andro-rasanter-v47) |
| 8 | Nittaku Hurricane Pro III Turbo Orange | Paddle Palace, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=n-h3-pro-t) |
| 9 | Andro Rasanter R50 | Go Table Tennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=andro-rasanter-r50) |
| 10 | Xiom Omega VII Hyper | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-vii-hyper) |
| 11 | Xiom Vega Korea | TableTennisStore, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-korea) |
| 12 | Xiom Omega VII Tour | eTableTennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-vii-tour) |
| 13 | Xiom Omega VII Asia | eTableTennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-vii-asia) |
| 14 | Butterfly Roundell Soft | Amazon (official), TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-roundell-soft) |
| 15 | Xiom Omega VII Euro | Go Table Tennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-vii-euro) |
| 16 | Xiom Vega Asia | TableTennisStore, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-asia) |
| 17 | Donic Desto F1 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=d-desto-f1) |
| 18 | Xiom Jekyll & Hyde V52.5 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-j-h-v525) |
| 19 | Xiom Vega Tour | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-tour-r) |
| 20 | Donic Desto F2 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=d-desto-f2) |
| 21 | DHS NEO Skyline 3 TG3 | Paddle Palace | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-skyline-3-neo-40) |
| 22 | DHS Skyline TG3 | Double Happiness USA, Paddle Palace | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-skyline-3-39) |
| 23 | Xiom Omega 8 Pro | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-8-pro) |
| 24 | Donic BlueGrip C1 | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=d-bluegrip-c1) |
| 25 | DHS Tin Arc | Table Tennis One Stop Shopping | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-tinarc-med) |
| 26 | DHS PF4 | Double Happiness USA | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-pf4) |
| 27 | Stiga Mantra PRO M | Go Table Tennis, Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=s-mantra-pro-m) |
| 28 | Tibhar Nimbus Soft | Table Tennis One Stop Shopping | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=t-nimbus-soft) |
| 29 | JOOLA Rhyzer 43 | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=j-rhyzer-43) |
| 30 | DHS Tin Arc 5 | Double Happiness USA, Megaspin | — |
| 31 | DHS Hurricane 9 Pink | Double Happiness USA | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-hurricane-9-pink) |
| 32 | DHS G888 | Double Happiness USA | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-g888) |
| 33 | Nittaku Flyatt Hard | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=nittaku-flyatt-hard) |
| 34 | Tibhar Nimbus | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=t-nimbus) |
| 35 | Xiom Vega X | Go Table Tennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-x) |
| 36 | Xiom Omega V Euro | eTableTennis | — |
| 37 | Tibhar Sinus | TableTennisStore | — |
| 38 | Xiom Omega VII Pro | eTableTennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-omega-vii-pro) |
| 39 | DHS G666 | Table Tennis One Stop Shopping | — |
| 40 | Tibhar Sinus Sound | Table Tennis One Stop Shopping | — |
| 41 | Xiom Vega Asia DF | TableTennisStore | — |
| 42 | Xiom Vega Japan | Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-japan) |
| 43 | Yasaka Original | Go Table Tennis | — |
| 44 | Xiom Jekyll & Hyde Z52.5 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-j-h-z525) |
| 45 | Tibhar Quantum S | Table Tennis One Stop Shopping | — |
| 46 | DHS Gold Arc 5 | Table Tennis One Stop Shopping | — |
| 47 | Tibhar Hybrid K2 | Table Tennis One Stop Shopping | — |
| 48 | Andro Hexer | TableTennisStore | — |
| 49 | DHS NEO Skyline 2 TG2 | Table Tennis One Stop Shopping | — |
| 50 | Butterfly Roundell Hard | eTableTennis | — |
| 51 | DHS Hurricane 2 (H2) | Table Tennis One Stop Shopping | — |
| 52 | DHS NEO Hurricane 2 | Table Tennis One Stop Shopping | — |
| 53 | Xiom Jekyll & Hyde V47.5 | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-j-h-v475) |
| 54 | Donic Slice 40 | TableTennisStore | — |
| 55 | Tibhar Rapid Soft | Table Tennis One Stop Shopping | — |
| 56 | Xiom Vega Intro | Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=xiom-vega-intro) |
| 57 | DHS Skyline TG2 | Table Tennis One Stop Shopping | — |
| 58 | Stiga Mantra H | Amazon (other seller) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=s-mantra-h) |
| 59 | DHS NEO Hurricane 3 Provincial (Blue Sponge) | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-h3-neo-prov-blue) |
| 60 | JOOLA Samba | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=j-samba) |
| 61 | Xiom Vega Elite | Amazon (other seller) | — |
| 62 | Stiga Mantra M | Amazon (other seller) | — |
| 63 | Tibhar Vari Spin | No US source found | — |
| 64 | Tibhar Vari Spin D.TecS | No US source found | — |
| 65 | Tibhar Speedy Spin | No US source found | — |
| 66 | Donic Vario Big Slam | No US source found | — |
| 67 | Donic Vario Soft | No US source found | — |
| 68 | Sanwei Target National | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=sanwei-target-national) |
| 69 | Sanwei Gear Hyper | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=sanwei-gear-hyper) |
| 70 | Victas TRIPLE Double Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-t-d-extra) |
| 71 | Victas V > 11 Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-11-extra) |
| 72 | Gewo Nexxus EL Pro 53 Superselect | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-el-pro-53-ss) |
| 73 | Victas V > 22 Double Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-22-d-e) |
| 74 | Gewo Nexxus XT Pro 48 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-xt-pro-48) |
| 75 | Gewo Nexxus EL Pro 48 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-el-pro-48) |
| 76 | Gewo Nexxus EL Pro 48 Superselect | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-el-pro-48-ss) |
| 77 | Victas VS > 401 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-vs-401) |
| 78 | Victas V > 15 Sticky | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-15-sticky) |
| 79 | Sanwei Ultraspin T88 | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=sanwei-ultraspin-t88) |
| 80 | Gewo Nexxus EL Pro 45 Superselect | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-el-pro-45-ss) |
| 81 | Victas V > 15 Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-15-extra) |
| 82 | Gewo Nexxus EL Pro 50 Hard | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-el-pro-50) |
| 83 | Gewo Nexxus EL Pro 43 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-pro-43-el) |
| 84 | Victas V > 20 Double Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-20-d-e) |
| 85 | Victas V > 20 Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-20-e) |
| 86 | Victas VJC > 07 Sticky Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-vjc-07-se) |
| 87 | Victas VS > 402 Limber | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-vs-402-limb) |
| 88 | Victas Ventus Extra | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-ventus-extra) |
| 89 | Gewo Inventus XT Pro 50.0 | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-inventus-xt-pro-50) |
| 90 | Gewo Nexxus XT Pro 50 Hard | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-xt-pro-50) |
| 91 | Gewo Proton Neo 325 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-proton-neo-325) |
| 92 | Victas VJ > 07 Regular | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-07-regular) |
| 93 | Gewo Neoflexx EFT 40 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nanoflexx-eft-40) |
| 94 | Gewo Neoflexx EFT 45 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nanoflexx-eft-45) |
| 95 | Gewo Nexxus EL Pro 38 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-pro-38-el) |
| 96 | Gewo Nexxus EL Pro 53 Hard | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nexxus-el-pro-53) |
| 97 | Gewo Codexx EL Pro 52 | TableTennisStore | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-codexx-el-pro-52) |
| 98 | Gewo Neoflexx EFT 48 | eTableTennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-nanoflexx-eft-48) |
| 99 | Victas V > 15 Stiff | Pending Megaspin review | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=victas-v-15-stiff) |
| 100 | Gewo Proton Neo 375 | eTableTennis | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=gewo-proton-neo-375) |

</details>

<details>
<summary>Megaspin manual review for previously covered entries</summary>

| Rubber | Megaspin manual review |
| --- | --- |
| Butterfly Dignics 05 | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-dignics-05) |
| Butterfly Dignics 09C | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-dignics-09c) |
| Butterfly Glayzer | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-glayzer) |
| Butterfly Glayzer 09C | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-glayzer-09c) |
| Butterfly Tenergy 05 | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-tenergy-05) |
| Butterfly Tenergy 05 FX | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-tenergy-05-fx) |
| Butterfly Tenergy 64 | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-tenergy-64) |
| Butterfly Zyre 03 | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=b-zyre-03) |
| DHS Hurricane 3 (H3) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-hurricane-3-39) |
| DHS Hurricane 3 (National) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-h3-n) |
| DHS Hurricane 3 National (Blue Sponge) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-h3-n-blue) |
| DHS NEO Hurricane 3 | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-h3-neo-39) |
| DHS NEO Hurricane 3 National (Blue Sponge) | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=dhs-h3-neo-n-bl) |
| JOOLA Dynaryz ZGR | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=j-dynaryz-zgr) |
| JOOLA Trinity Charged | [Unverified listing](https://www.megaspin.net/store/default.asp?pid=j-trinity-charged-h-c) |

</details>

## Home discovery page (2026-11-22)

- Home now puts a compact upload target first, then the four shoppable gear picks, the two-tap quiz, five cached feature demos, the before/after strip, and a footer linking to the main pages. The health check replaces the drop zone on failure. All five demo destinations still open when the analysis server is unreachable.
- Playwright Chromium checked the production build at the reference width of 1036 px, at 1440 px, and at 375 px with touch emulation. Verified both themes, offline retry and keyboard upload, quiz handoff, hover and tap previews, before/after playback, reduced motion, the paddle cursor, the background ball, and the absence of horizontal page overflow. The browser integration was missing its Chrome executable, so the checks used the locally installed Chromium.
- Compared the layout reference with the production captures for hero copy and size, section order, typography and palette, the four-card rail and quiz, the five-tile grid, video framing, and footer navigation. Reframed the portrait clips in the smaller feature tiles and aligned the four buy buttons. The shared header stayed in its existing layout, and the full demo player shows the portrait frame with its coaching overlays intact. The hero copy matched the reference text.
- Three Lighthouse 13.6 mobile runs against the local production builds scored **87, 91, 93** before and **94, 98, 98** after. Median Performance rose from **91 to 98**. Median LCP was 0.8 s before and 0.9 s after, median total blocking time fell from 380 ms to 170 ms, and CLS was zero throughout. Every initial load requested zero MP4s.
- Frontend lint and build passed, along with all 179 frontend tests. Regenerating Home media from the cached examples reproduced the committed files byte for byte on this checkout.

# HANDOFF

Read this first, then `PROGRESS.md` (history, every measurement) and `AGENTS.md` (layout,
conventions). Last updated 2026-11-18 after the Coach result page fix, the licensing brief, the Coach speed brief
(Phases 0-4) and the player-picker brief before it. Work is on `main`; each change is its own
commit. All metrics are development data (no held-out set).

## Coach result page (bug brief of 2026-11-18, latest)

Reported:
- **A:** at 1920 px the plan wrapped one word per line, "100%" overlapped the cards, and the
  page scrolled sideways.
- **B:** "Coach's notes (2 files)" showed the internal /facts.json and /rallies.json as raw JSON.

Root cause of A: the grid was `lg:grid-cols-[minmax(0,22rem)_1fr]`. A `1fr` track can't shrink
below its widest content, and a raw JSON line in the notes' `<pre>` was thousands of pixels wide.
That pushed the right column past the page and squeezed the plan column to almost nothing.

Fixes:
- **Layout:** every track is now `minmax(0, ...)`, with `min-w-0` on the columns and
  `overflow-wrap:anywhere` on long text. The same fix went on the Breakdown/Match page grid and
  the breakdown details.
- **Plan** (`frontend/app/jobs/[id]/coach-view.tsx`): a compact checklist with a progress bar and
  "n of 6 · %" while running. When done it collapses to one "All steps done" line that opens. On
  failure the list stays open and marks where it stopped.
- **Notes:** "Your coaching" is the main section. It renders `job.coaching.markdown` with
  `app/markdown.tsx`, a small renderer that outputs React text only (no HTML).
  - The backend fills `coaching` = `{markdown, fix, drill}` from every engine (`agent/notes.py`):
    the coaching call, offline cards (now Markdown with numbered fixes), the deep agent and the old
    fixed plan. It's null until written.
  - With no notes, the page says so with the reason (`warning`).
  - The working files appear only under a Debug toggle in `next dev`.
  - The breakdown no longer repeats the drill.
- **Old jobs:** jobs without the field (the cached demos, older jobs) show their `summary`.

Checked:
- Headless Chrome at 375, 768 and 1920 px, dark and light: a running job, a new done job (also
  with everything expanded), the reported job 39d38550 and all four demo jobs. No horizontal
  scroll on any of them. Each plan step fits on one line at 1920 px, and the plan column is 352 px.
- Live Coach jobs on coaching-demo and match_b ended with `coaching` set (offline cards: `make dev`
  has no API key).
- Tests: frontend 172 pass (`test/coach-view.test.ts`, including a check that no result-page grid
  uses a bare `1fr`); `tsc` clean; backend Coach/API/worker tests 164 pass, 1 skipped.
- Not checked: the full backend suite (it was run out of memory beside `make dev` before) and
  `next build` (dev server running).

## Licensing (brief of 2026-11-18)

The user plans to sell the whole app. No app logic changed.
- `LICENSE`: BSL 1.1. Every word from "Terms" to the end is identical to the SPDX `BUSL-1.1`
  text; the Parameters and Notice blocks follow MariaDB's layout.
  - Licensor: Duke (iambmd). Licensed Work: TTSkill (all code in this repository).
  - Additional Use Grant: personal and non-commercial use, in the user's words.
  - Change Date: 2030-11-18. Change License: Apache-2.0.
  - Contact for other licensing: https://github.com/iambmd. The user's email was not put in
    public files.
- `THIRD_PARTY_LICENSES.md`: every Python distribution (91, from `.venv` metadata), every npm
  package (200, from the lockfile), plus the system tools, fonts, models, datasets, footage and
  data. Eleven items are flagged at the top.
- README has a License section; `frontend/package.json` (and the lockfile root) has
  `"license": "SEE LICENSE IN LICENSE"`; AGENTS.md "Adding things" says to record licenses.

Open, for the user to decide before selling:
- **Blocks commercial use as it is:**
  - YouTube footage of pros (pro clips, the pros' breakdowns in Match/Coach, and the committed
    Ma Long and match-after demo videos)
  - the YouTube link input (yt-dlp; it also pulls in GPL `mutagen`)
  - OpenTTGames (CC BY-NC-SA, eval only today)
  - RevSpin rubber ratings
  - hotlinked product photos
- **Medium:** Commons pro photos without credit; pros' names and likeness; the @swift_TT-derived
  style profile; consent from the people in the user's own demo videos.
- **Covenant 2 of the BSL** says the Additional Use Grant must not add restrictions. The grant's
  second sentence ("Any commercial use ... requires a commercial license") could be read as
  narrowing the BSL's own non-production grant. Lawyer to confirm; a fix is "Any commercial
  production use ..." or dropping that sentence. Kept verbatim as the user asked.
- Each future release should bump the Change Date (it is fixed at 2030-11-18 for every version
  until changed).

## Current state

| Thing | Metric |
| --- | --- |
| Auto-Cut rally F1 (`eval.run --pose`, IoU >= .5) | coach_demo .500, match_b .629, 720p montage .722 |
| IMG_8782 Auto-Cut regression | 10/10 real rallies kept, 0/4 non-play kept |
| Identity audits, 12 frames each | IMG_8782 12 correct / 0 wrong / 0 abstained; match_b 8 / 0 / 4 |
| Coached stroke selection (8 peaks labelled from frames) | 5/5 real strokes kept, 3/3 post-point turns/walks rejected |
| Coach end to end | coaches the user on IMG_8782, coach_demo, both montage encodes (frame-checked) |
| Forehand/backhand auto-detection | fails its one labelled case (strict xfail); geometry candidate rejected |
| Player lookup, real Chrome, 12 frames | IMG_8782 3.2 s end to end (grab 0.96 s, answer 2.19 s); coaching-demo 4.1 s; HEVC fallback (238 MB) ~12 s locally (upload ~3 s, server 6.9 s, Next.js +1.4 s) |
| Players found (12 rally frames) | IMG_8782 2 (was 3), coach_demo 2 (was 3), montages 3 players + table leg as "still" |
| Tests | backend 399 pass, 3 skips, 1 xfail; frontend 156 pass; build passes |

Samples (git-ignored `samples/`): `IMG_8782.MOV` (3:35 continuous match, phone far back),
`coach_demo.mp4` (640x360 drill), `match_b.mp4` (480p montage, 18 clips, crossfades),
`coaching-demo.mp4` (same montage at 720p; shares match_b's labels via `"also"`). The user is
the teal "CHINA" shirt, right-handed, 168 cm. OpenTTGames videos: ignored `data/openttgames/`
(~1.9 GB of the 10 GB cap).

## Done this session (player-picker brief of 2026-11-18)

How it was checked: a real headless Windows Chrome driven over CDP from a scratch script
(`node.exe` on the Windows side; WSL can't reach Windows' localhost), plus curl from both sides
of WSL. A second Chrome with `--disable-features=PlatformHEVCDecoderSupport` stands in for Chrome
without an HEVC decoder (this machine's Chrome decodes iPhone HEVC through Windows).

| Commit | Change | Measured |
| --- | --- | --- |
| f4b299e | 1/1b: every lookup logged on all three hops (browser console `[players]`, Next.js `[players/detect]`, backend `players/detect ...`) with frame times, people per frame and the time split; `timing` covers read/wait/decode/download/sample/probe/detect/total + `next_s`; link probe off the event loop; link download cancellable; model warmed at startup (`TTSKILL_WARM=0` off); links get 120 s | Frames path 1.4-1.6 s end to end (Next.js adds 0.01-0.05 s, upload 0.7-1 MB is not a factor). The 28.8 s / 30 s requests could not be reproduced on the frames path, idle or under a running Coach job (2.2-2.4 s). They match the link path: probe 9.9 s + download 5.8 s + sample + detect = 20.3 s for a 32 s video while timing.seconds said 3.06, and the probe blocked every other request. /health now stays at 11 ms during a link lookup |
| 7fda7e4 | 2: 12 frames over the whole video (browser), ffmpeg rally-preferred frames on the server (9 in rallies, 3 anywhere; 2 decoder threads x 6), coarse-to-fine order under the budget, duplicate skeletons merged (shoulders < 0.25 torso, or a box inside another), table-leg bodies dropped, groups rejoined, 2 sightings instead of a third of frames, best frame = most players then biggest | Duplicates measured 0.02-0.11 torso apart vs >= 1.8 for different people; table legs thighs 0.77-1.83 torsos not going down vs 0.33-0.43 for misfits on real people. 12 HEVC frames 1.0 s (was 3.4 s sequential) |
| 2edfdc4 | 3: 0 -> "We couldn't spot a player" + Analyse anyway (submit waits); 1 -> "Analysing this player" + Change player; 2+ -> always the picker. Stub/demo answer `available: false` | Checked in Chrome on a single-player crop, a test pattern, IMG_8782 |
| 83d99b7 | 3b: background people (box moves < 0.05 box heights, far from a found blue/green table, tiny) go to `others`, behind "Show everyone we saw"; typical sighting for thumb/seed; average-linkage regrouping. "Only me in the video" on Coach/Breakdown -> `only_me=1` -> `people.most_active` (16 moments x 2 frames 0.2 s apart, limb motion weighted by relative size) | Players' box motion 0.083-0.594, table leg 0.045. most_active = the user on IMG_8782 and coach_demo; a Breakdown with only_me ran end to end |
| d8d133b | 4: unreadable video -> the picker uploads it to /players/detect (progress, Analyse anyway stops it) -> ffmpeg frames -> `staged` token -> the job takes the token, the file is not sent again | Chrome without HEVC on IMG_8782: fallback in 0.2 s, 2 players, submit ~1 KB, job on input.mov |
| 543e503, 1ab8d96 | 5: real-video tests: late entrant (IMG_8782 with 30 s black), one person (crop), nobody (test pattern), HEVC (libx265); tap-then-track test moved to 12 frames, players only, first 2 s | Full suites green |

Browser steps to check it yourself (`make dev`, Chrome, DevTools console open):
1. /coach, choose `samples/coaching-demo.mp4`: "Finding the players" for ~3-4 s, then "We see
   N players" with a frame and thumbnails. The console prints `[players] drew 12 frames ... answer
   in ... (Next.js ..., backend ..., detect ...); people per frame ...`; the `make dev` terminal
   prints the matching Next.js and backend lines.
2. /breakdown, choose `IMG_8782.MOV`: "We see 2 players" (you and your opponent), one thumbnail
   each. Tap yourself; submit unblocks.
3. Tick "Only me in the video" before choosing a file: no lookup, no picker, submit enabled.
4. A video with one person (e.g. crop IMG_8782 with
   `ffmpeg -ss 95 -t 30 -i IMG_8782.MOV -vf crop=iw*0.56:ih:iw*0.44:0 single.mp4`): "Analysing
   this player" + Change player. A video with nobody: the message + "Analyse anyway".
5. HEVC fallback: start Chrome with `--disable-features=PlatformHEVCDecoderSupport` (or use a
   browser without HEVC) and choose IMG_8782.MOV: "Your browser can't read this video, so we're
   sending it... N%", then the picker; on submit the Network tab shows a ~1 KB job POST.

Not re-verified: a staged-upload job run to the end (the one started in the browser test was
killed by a `--reload` when a test file under backend/ changed; job creation and the stored
input were checked). Links still need YouTube's probe (2-10 s) and a full download, so they
can't be under 5 s; the job submit probes the link again.

## Earlier session (user brief of 2026-11-17)

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

0. **User brief of 2026-11-18 (later): make Coach fast and cheap** (Phases 0-4: time every
   stage; fixed pipeline + one structured Claude call with caching; hit-window pose; parallel
   render/matching; caches; partial results; eval of YOLO-pose/RTMPose + ByteTrack in eval/;
   RQ worker; then resume 1b with test_5 = both players left-handed, confirmed by the user).
   Progress is recorded below as each phase lands.
   - Phase 0 done (`e4c07be`): `backend/timing.py` + `scripts/time_coach.py`; records in
     `backend/eval/coach_speed/`. Deep agent (Opus 5.5), demo request: coaching-demo 242 s / $0.36,
     IMG_8782 297 s / $0.35; 19 Claude calls (105-116 s, mostly serial), floor-bounce check 45-65 s,
     choose_window 28-42 s, full-rate pose on the same window x3 (~17-23 s each), breakdown rendered
     x2 (~20 s each), vision analyzer 14-16 s whose text is replaced.
   - Phase 1 done (`aedbd03`, `220064c`, `626ae6d`, `e41e7b8`): fixed pipeline (`agent/fixed.py`) +
     one cached structured Sonnet 5.5 call at effort medium (`agent/brief.py`); pose at the strokes
     (`technique/hitpose.py`); per-video cache (`app/cache.py`); 720x1280 render of the coached stroke.
     | | Phase 0 agent | Phase 1 first time | Phase 1 same video again |
     | coaching-demo | 242 s, $0.36 | 83.6 s, $0.025 | 23.0 s, $0.016 |
     | IMG_8782 | 297 s, $0.35 | 122.7 s, $0.016 | 29.4 s, $0.018 |
     First-time runs are dominated by the pose-based play check (56-83 s, in the background, only
     the reel needs it) and pose at the strokes (42-67 s; both slow each other down). Records:
     `backend/eval/coach_speed/phase1-*.json` (effort default vs medium in `phase1-effort-*`).
     Quality: same shape and first fix as the agent on coaching-demo (knees 157° vs 158°, same pros).
     Open: the elbow advice can contradict itself because the contact angle (128° vs Fan 161°) and
     the DTW note ("16° straighter than Fan") disagree; the agent quoted the same note.
     Not done: follow-up questions (the deep agent is kept behind COACH_ENGINE=agent, not wired to a
     follow-up endpoint).
   - Phase 2 done (`3420adf`, eval only): `backend/eval/pose_models.py`, results in
     `backend/eval/pose_models_results.json`. s/frame MediaPipe+tracker 0.093, RTMPose-m 0.580,
     RTMPose-lite 0.148, RTMO-m 0.277. Far player found in play: 0.26-0.42 (MediaPipe) vs 0.52-0.87.
     Identity on the montage (match_b): ours 9/0/2, ByteTrack models 4-5 wrong of 11; continuous
     match: all tie. Bat wrist seen at 4 strokes: 0.45 vs 0.79-0.83. Recommendation: don't switch;
     next try RTMPose-lite for detection on few frames (picker, coached clip) with our identity on top.
     The eval venv is `backend/eval/work/venv-pose` (git-ignored; how to make it is in the script).
   - Phase 3 done (`78ee64d`; fix `0507bed`): SQLite queue (`app/jobqueue.py`; Redis not installed,
     no sudo) + `python -m app.worker` (`make dev` starts it): a spawned process per job, 15 min limit
     (Auto-Cut 30), OOM/timeout/dead-worker all end the job failed with a message; a `prepare` lane
     fills Coach's per-video cache at upload (cache entries locked across processes). API reloads no
     longer kill jobs (checked live). `TTSKILL_INLINE=1` = old in-API mode (tests).
     Fix found on the way: a slow-stroke stretch (pushes, 3.1 torso/s peak) found "no strokes";
     `hitpose.find_own` now relaxes the 5 torso/s bar when nothing passes.
   - Phase 4 done (`03c4ea3`, `bd35bfe`, `a3c9fc0`): test_5 both left-handed recorded as user-confirmed
     ground truth; test_1 verified on frames (both right-handed; red-rubber cue was wrong there).
     `eval/train_wing.py` (logistic regression + abstain, calibration test_7/test_5/test_1 = 135,
     frozen, validation test_6/test_3 once): 1b wing 9 decisions, precision 0.889 (gate 0.9, fails by
     one), hybrid 31/47 vs 30/47; 1c block: no block found (7 in validation), hybrid = baseline. Both
     not promoted; samples/strokes/ doesn't exist, so OpenTTGames only. Blocks are now pickable stroke
     types (Breakdown form, prompt, offline templates), never auto-detected.
     Raw `data/openttgames/test_1.mp4` and `test_5.mp4` (1.77 GB) are still on disk: the agent's
     delete was blocked by the permission check; delete them by hand (pose windows are cached).


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
2. **1b: learned forehand/backhand classifier** (done 2026-11-18, not promoted; see 0. Phase 4).
   Next if resumed: more calibration data with verified hands (test_4: 71 strokes, 2.25 GB; the
   game_* videos) and the user's own labelled clips in samples/strokes/. Earlier notes: Cached pose windows: test_7 41
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

- Player lookup: a partner seen only twice in the same spot on a montage reads as "still"
  (background), and a small split-off of the user can land in `others`; both stay tappable via
  "Show everyone we saw". Table "far" only works for blue/green tops (grey tables never count).
- `uvicorn --reload` watches backend/tests too (only matters with TTSKILL_INLINE=1 now).
- The worker runs one job at a time by default (TTSKILL_WORKERS); a second job waits in the queue.

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

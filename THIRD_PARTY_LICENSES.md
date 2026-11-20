# Third-party licenses

TTSkill's own code is under the Business Source License 1.1 ([LICENSE](LICENSE)). This file covers
everything else the app uses or the repository contains: software dependencies, system tools,
fonts, models, datasets, footage and data. **These keep their own licenses and terms. They are not
part of the Licensed Work, and the BSL grants no rights in them.**

Audited on 2026-11-18 from:
- `backend/.venv`: the package metadata of all 91 installed Python distributions
- `frontend/package-lock.json`: the `license` field of all 200 npm packages
- the model card and the dataset pages
- the files committed to the repo

This is an engineering inventory, not legal advice. Have a lawyer review the flagged items before
selling the app.

## Flagged: blocks or limits commercial use

| # | What | Where | Problem | Suggested replacement |
| --- | --- | --- | --- | --- |
| 1 | **Pro footage from YouTube** | Pro clips: 9 YouTube links in `backend/data/players/players.json` and 8 hand-downloaded clips in `backend/data/players/manual/` (both git-ignored). They are rendered into the pros' breakdowns, which are served in Match results and Coach's `pro_matches.mp4`. | The footage belongs to the broadcasters and uploaders (WTT/ITTF, channels). YouTube's Terms of Service forbid downloading except where YouTube offers it. Commercial reuse needs the rights holders' permission. | License footage (WTT/ITTF media licensing, or a channel's written permission), or film your own reference players with signed releases. Alternatively, ship only the computed numbers (`profiles.json`: limb ratios, angle curves) and show the pro as a skeleton or a drawing, not video. |
| 2 | **Committed demo videos with third-party footage** | `frontend/public/examples/breakdown-before.mp4`, `breakdown-after.mp4` and `frontend/public/demo/breakdown.mp4` (a Ma Long clip); `frontend/public/examples/match-after.mp4` (the matched pros' breakdowns) | The same footage rights as #1, and these files are published on the site and in the repo. | Re-shoot the Breakdown and Match examples with a player who signs a release, then run `scripts/refresh_demos.py`. |
| 3 | **YouTube link input** | `backend/app/download.py` (yt-dlp) on every form; `backend/style/fetch_refs.py`; `backend/players/build.py` | A paid service that downloads YouTube videos breaks YouTube's Terms of Service, whatever yt-dlp's license (Unlicense) allows. It also pulls in `mutagen` (GPL-2.0-or-later, #6). | Uploads only in the commercial version. If links matter, users download their own video first, or you use an official API with the creator's permission. |
| 4 | **OpenTTGames and Extended OpenTTGames** (CC BY-NC-SA 4.0) | Eval only: `backend/eval/` (raw videos git-ignored in `data/openttgames/`). Committed derivatives: `backend/eval/wing_model.json`, `block_model.json`, `*_validation.json`, `labels/openttgames_hands.json` (our own hand labels on their videos). | Non-commercial and share-alike. A model trained on it, or data derived from it, can't ship in a paid product. The app ships none today: both classifiers stayed in `eval/`. | Keep it eval-only. Train anything you ship on your own labelled clips (`samples/strokes/`), or on data licensed for commercial use. |
| 5 | **Rubber ratings from RevSpin** | `backend/equipment/rubbers.csv`, `frontend/lib/rubbers.json` (984 rubbers, revspin.net user ratings, via PingSense) | RevSpin's Terms of Use say its content is copyrighted and may not be reproduced in any other format. | Get RevSpin's permission or a data license; or build the table from manufacturers' published specs plus your own users' ratings. |
| 6 | **mutagen** (GPL-2.0-or-later) | Backend Python, pulled in by `yt-dlp[default]` (`backend/requirements.txt`) | GPL. It's fine on your own server (GPL-2.0 has no network clause), but shipping the backend to customers (on-premise, desktop, Docker image) would put GPL code in the same process as TTSkill. | Dropping YouTube links (#3) removes it. Otherwise install `yt-dlp` without the `[default]` extra. |
| 7 | **Product photos** | `frontend/lib/product-images.json`: hotlinked from Butterfly, Tibhar, Nittaku, andro, JOOLA, Megaspin, Paddle Palace and tokspin. The file itself says "non-commercial hackathon demo". | The photos are copyrighted and the logos are trademarks. Hotlinking also depends on their servers. | Join the brands' or retailers' affiliate or partner programs, which grant image use; or use the drawn fallback the cards already have. |
| 8 | **Pro photos from Wikipedia** | `frontend/app/pros/pro-photo.tsx`: the lead image from Wikimedia Commons, fetched in the browser | Commons images carry their own licenses (often CC BY or CC BY-SA), which require the author and license to be credited. The app only links the page. | Show each image's author and license, read from the Commons API (`extmetadata`); or drop the photos. |
| 9 | **Pros' names and likeness** | Find my pro match, `/pros`, Coach ("closest pros: Ma Long 84%") | Facts such as height or bat hand are fine. Using real athletes' names and images to sell a product can raise publicity-rights and implied-endorsement claims. | Have a lawyer review it. Keep the wording factual, add a "not affiliated with or endorsed by" line, and use no photos of them (#8) or footage (#1) without a license. |
| 10 | **Coaching-style profile from a YouTube channel** | `backend/style/swift_style.json` (committed: measurements in our own words); references downloaded by `backend/style/fetch_refs.py` from @swift_TT (git-ignored, never served). `backend/eval/README.md` also lists @swift_TT Shorts as eval stroke examples. | The measurements (pacing, layout) aren't footage, and a style isn't copyrightable. But the download breaks YouTube's Terms of Service, and the file name points at one creator. | Ask the creator, or re-derive the profile from videos you own or license. Rename the file (e.g. `coach_style.json`) and remove `fetch_refs.py` from the commercial build. |
| 11 | **People in your own demo videos** | `frontend/public/examples/autocut-before.mp4`, `coach-before.mp4`, `match-before.mp4` and the After videos made from them (your matches and drills) | You own the footage, but opponents and partners appear in it. Marketing a paid product with them needs their consent. | Get a signed release from each person shown, or crop or blur them. |

## Fine with conditions

| What | License | Condition |
| --- | --- | --- |
| **FFmpeg** (system tool, called as a separate program: `ffmpeg`/`ffprobe`) | This machine's Ubuntu build (8.0.1) is configured `--enable-gpl --enable-libx264 --enable-libx265`, so it is GPL-2.0-or-later as built | Running it on your server is fine, and calling it as a separate process keeps TTSkill's code out of the GPL. If you ship it to customers (a Docker image, an installer), include its license and offer its source. An LGPL build (no libx264) avoids the GPL. |
| **H.264 encoding** (libx264, used by `technique/media.py` and `app/cut.py`) | Patent pool (Via LA AVC/H.264) | Pool royalties can apply to commercial encoders and paid video services. Check Via LA's current AVC terms before charging users. x264 LLC also sells commercial x264 licenses if you ever distribute it. |
| **sharp / libvips** (npm `@img/sharp-libvips-*`, optional for Next.js) | LGPL-3.0-or-later (sharp itself Apache-2.0) | Unmodified and dynamically linked, so no action is needed. The app doesn't use `next/image`, so it is installed but unused. |
| **MediaPipe Pose Landmarker** (`pose_landmarker_full.task`, BlazePose GHUM 3D), downloaded at run time by `technique/pose.py` | Apache-2.0 (model card: "LICENSED UNDER Apache License, Version 2.0") | Commercial use is allowed; keep the notice. The card lists multiple people in an image, people too far away, and any surveillance or identity recognition as out-of-scope uses. These are not license terms, but the app asks for up to 3 poses per frame and follows players by clothing colour, so don't market the tracking as identity recognition. |
| **Claude** (Anthropic API, `anthropic`, `langchain-anthropic`) | A service under Anthropic's Commercial Terms and Usage Policy, not a license we redistribute | Commercial use is allowed under those terms. The app sends frames of users' videos to Anthropic, so the product's privacy policy must say so. |
| **Barlow, Barlow Condensed** fonts (`backend/technique/fonts/`, plus `next/font/google` in the frontend) | SIL Open Font License 1.1 (`backend/technique/fonts/OFL.txt`) | You may bundle them and use them commercially. Keep `OFL.txt`, and don't sell the fonts on their own. |
| **ESLint** and **eslint-config-next** (frontend development dependencies, added 2026-11-20) | MIT for both | Used for lint checks. The frontend lockfile records licenses for their transitive dependencies. |
| **caniuse-lite** (npm, used by the build) | CC-BY-4.0 | Data used at build time; the attribution is in its package. |
| **lightningcss** (npm, Tailwind's CSS engine, dev only), **certifi**, **orjson** (Python) | MPL-2.0 (orjson: MPL-2.0 AND (Apache-2.0 OR MIT)) | File-level copyleft, which only applies if you modify those files. |
| **Pro facts** (heights, bat hands, grips, equipment setups in `players.json` and `frontend/lib/pros.json`, from Wikipedia, Olympedia, ultraspin, tabletennisteacher and others) | Facts aren't copyrightable; the source pages keep theirs | Keep the per-player sources (they're in the files), and don't copy page text. See #9 for the names. |

Not used anywhere: **YOLO / Ultralytics** (AGPL-3.0, or a paid Enterprise license). The Phase 2
pose experiment (`backend/eval/pose_models.py`, separate eval venv, not in any requirements file)
used rtmlib 0.0.16 (Apache-2.0), onnxruntime 1.32.0 (MIT), and OpenMMLab's RTMPose, RTMO and YOLOX
weights (Apache-2.0). Their training sets (COCO, AI Challenger, and others) have their own terms;
check those before using any of them in production. If a YOLO-style one-stage model is wanted, use
RTMO or YOLOX rather than Ultralytics.

## Backend (Python)

### Direct dependencies

`backend/requirements.txt` and `backend/technique/requirements.txt`, with the versions installed in `backend/.venv`:

| Package | Version | License |
| --- | --- | --- |
| fastapi | 0.115.12 | MIT |
| uvicorn[standard] | 0.34.2 | BSD-3-Clause |
| python-multipart | 0.0.20 | Apache-2.0 |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| scipy | 1.18.1 | BSD-3-Clause |
| httpx (tests) | 0.28.1 | BSD-3-Clause |
| pytest (tests) | 8.3.5 | MIT |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 (the wheel bundles FFmpeg libraries under the LGPL) |
| mediapipe | 1.2.3 | Apache-2.0 |
| pillow | 13.0.0 | MIT-CMU |
| pydantic | 2.14.3 | MIT |
| anthropic | 2.8.0 | Apache-2.0 |
| yt-dlp[default] | 2026.10.26 | Unlicense (extras include mutagen, GPL-2.0-or-later: flag #6) |
| deepagents | 0.7.38 | MIT |
| langchain-anthropic | 1.7.10 | MIT |

### Everything installed (91 distributions), by license

- **MIT:** annotated-types, anyio, bracex, brotli, charset-normalizer, deepagents, docstring_parser, fastapi, filetype, fonttools, h11, httptools, iniconfig, jiter, langchain, langchain-anthropic, langchain-core, langchain-google-genai, langchain-protocol, langgraph, langgraph-checkpoint, langgraph-prebuilt, langgraph-sdk, langsmith, pip, pluggy, pydantic, pydantic_core, pyparsing, pytest, pyyaml, sounddevice, truststore, typing-inspection, urllib3, watchfiles, wcmatch
- **MIT-0:** cffi. **MIT-CMU:** pillow.
- **MIT OR Apache-2.0:** ormsgpack, sniffio, uvloop.
- **Apache-2.0:** absl-py, anthropic, distro, flatbuffers, google-auth, google-genai, mediapipe, opencv-contrib-python (a mediapipe dependency), opencv-python-headless, opentelemetry-api, python-multipart, requests, requests-toolbelt, tenacity, tzdata
- **Apache-2.0 OR BSD:** cryptography (BSD-3-Clause), packaging (BSD-2-Clause).
- **BSD-3-Clause:** click, contourpy, cycler, httpcore, httpcore2, httpx, httpx2, idna, jsonpatch, jsonpointer, kiwisolver, pycparser, python-dateutil, python-dotenv, scipy, starlette, uuid_utils, uvicorn, websockets, zstandard
- **BSD-2-Clause:** pyasn1, pyasn1_modules, xxhash. **BSD / public domain:** pycryptodomex.
- **BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0:** numpy.
- **PSF-2.0:** typing_extensions. **matplotlib License** (PSF-based, permissive): matplotlib.
- **MPL-2.0:** certifi; orjson (MPL-2.0 AND (Apache-2.0 OR MIT)).
- **Unlicense:** yt-dlp; yt-dlp-ejs (Unlicense AND MIT AND ISC).
- **GPL-2.0-or-later:** mutagen (flag #6).

No AGPL and no non-commercial licenses.

## Frontend (npm)

### Direct dependencies (`frontend/package.json`)

| Package | Version | License |
| --- | --- | --- |
| next | 15.5.28 | MIT |
| react, react-dom | 19.1.1 | MIT |
| server-only | 0.0.1 | MIT |
| tailwindcss, @tailwindcss/postcss (dev) | 4.1.x | MIT |
| postcss (dev) | 8.5.x | MIT |
| typescript (dev) | 5.9.2 | Apache-2.0 |
| vitest (dev) | 3.2.x | MIT |
| @types/node, @types/react, @types/react-dom (dev) | 22.15.3, 19.1.12, 19.1.9 | MIT |

### Everything in the lockfile (200 packages), by license

Runtime (ships with or builds the site; `*` = optional, installed per platform):
- **MIT (20):** next, react, react-dom, scheduler, server-only, client-only, styled-jsx, nanoid, postcss, @next/env, @next/swc-* (8), @emnapi/runtime*, @img/colour*
- **Apache-2.0 (15):** @swc/helpers, detect-libc, sharp* and @img/sharp-* (12)
- **LGPL-3.0-or-later (14):** @img/sharp-libvips-* (10). Combined with Apache-2.0: @img/sharp-win32-* (3) and @img/sharp-wasm32* (with MIT). See "Fine with conditions".
- **ISC:** picocolors, semver*. **BSD-3-Clause:** source-map-js. **0BSD:** tslib. **CC-BY-4.0:** caniuse-lite.

Development only (tests, CSS build; not shipped):
- **MIT (126):** vitest and @vitest/*, vite, rollup and @rollup/*, esbuild and @esbuild/*, tailwindcss, @tailwindcss/*, @types/*, chai and its helpers, and the other small build tools
- **MPL-2.0 (11):** lightningcss and its platform binaries
- **BlueOak-1.0.0 (5, permissive):** chownr, graceful-fs, minipass, tar, yallist
- **ISC:** @isaacs/fs-minipass, siginfo. **Apache-2.0:** typescript, expect-type.

No GPL, AGPL or non-commercial licenses.

## Models

| Model | Used by | License | Notes |
| --- | --- | --- | --- |
| MediaPipe Pose Landmarker full (BlazePose GHUM 3D) | the app (`technique/pose.py`) | Apache-2.0 | See "Fine with conditions" |
| Claude (claude-sonnet-5-5 for Coach, claude-opus-5-5 for the Breakdown analyzer and the optional deep agent) | the app, when `ANTHROPIC_API_KEY` is set | Anthropic Commercial Terms (a service) | Without a key the offline templates are used |
| `backend/app/onset_model.json` (play-window classifier, git-ignored) | Auto-Cut and Coach rally detection when present | Ours | Trained on your own clips (coach_demo, match_b) by `eval/train_onset_model.py` |
| `backend/eval/wing_model.json`, `block_model.json` | eval only | Ours, but trained on OpenTTGames (CC BY-NC-SA 4.0) | Flag #4: don't ship |
| RTMPose-m/s, RTMO-m, YOLOX-m/tiny (rtmlib) | eval only (`eval/pose_models.py`) | Apache-2.0 | Training-data terms to check before any production use |
| YOLO / Ultralytics | not used | AGPL-3.0 or Enterprise | Don't add it |

## Datasets, footage and data

| What | Where | Terms | Status |
| --- | --- | --- | --- |
| OpenTTGames ([lab.osai.ai](https://lab.osai.ai)) and Extended OpenTTGames ([moamal01/table_tennis_data](https://github.com/moamal01/table_tennis_data)) | `data/openttgames/` (git-ignored), `backend/eval/work/` (git-ignored), derivatives in `backend/eval/` | CC BY-NC-SA 4.0 (rechecked on both sites 2026-11-16 and 2026-11-17, see `backend/eval/README.md`) | Eval only; flag #4 |
| TTStroke-21, P2ANet | not downloaded | gated / custom | not used |
| Pro clips (YouTube) | `backend/data/players/` (git-ignored) and the videos made from them | rights holders' copyright; YouTube Terms of Service | Flag #1 |
| Pro profiles | `backend/data/players/profiles.json` (committed) | our measurements from the clips in #1 | Numbers, not footage; they depend on #1 for provenance. Re-measure from licensed footage when #1 is replaced |
| Style references (@swift_TT) | `backend/data/style_ref/` (git-ignored); `backend/style/swift_style.json` | YouTube Terms of Service | Flag #10 |
| RevSpin rubber ratings | `backend/equipment/rubbers.csv`, `frontend/lib/rubbers.json` | RevSpin Terms of Use | Flag #5 |
| Product photos (hotlinked) | `frontend/lib/product-images.json` | manufacturers' and retailers' copyright and trademarks | Flag #7 |
| Pro photos (Wikimedia Commons, fetched live) | `frontend/app/pros/pro-photo.tsx` | per-image CC licenses | Flag #8 |
| Your own videos | `samples/` (git-ignored); `frontend/public/examples/{autocut,coach,match}-before.mp4` and their After videos | yours; other people appear in them | Flag #11 |
| Ma Long clip | `frontend/public/examples/breakdown-*.mp4`, `frontend/public/demo/breakdown.mp4` | third-party footage | Flag #2 |
| Eval labels for your clips | `backend/eval/labels/coach_demo.json`, `match_b.json`, `backend/eval/regressions/` | ours | fine |

## Keeping this file current

When you add a Python or npm dependency, a model or a dataset:
- add it here with its license
- check that it isn't AGPL, GPL (in-process), non-commercial or share-alike, and that it isn't YouTube footage
- if it is, keep it out of the shipped app (eval only, git-ignored)

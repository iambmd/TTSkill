# Data source

`rubbers.csv` is copied unchanged from Duke's PingSense project:
https://github.com/iambmd/Pingsense/blob/ea72d58/data/table_tennis_rubbers.csv

984 rubbers from 52 brands, with price and 0-10 user ratings (Speed, Spin, Control, Tackiness,
Weight, Sponge Hardness, Gears, Throw Angle, Consistency, Durability, Overall) collected from
revspin.net user reviews. Cells revspin doesn't publish are `TBD`.

The data has no rubber-type or thickness column. `recommend.py` reads anti-spin from the name
and treats the rest as inverted; it has no short or long pips rubbers yet. Thickness is advice
per level, not a filter.

`frontend/lib/rubbers.json` is the same data in JSON for the web app's offline mode
(regenerate with `python -m equipment.recommend --export ../frontend/lib/rubbers.json`).

US purchase links live separately in `shared/rubber-buy-links.json`. The recommenders join
them by exact name, so regenerating the ratings export preserves the purchase catalog.

## Blades (added 2026-11-24)

`blades.json` is the blade dataset: 562 blades with 10 or more RevSpin ratings, one object each (the same file is exported to
`frontend/lib/blades.json`). `blades_skipped.csv` lists the other 3,203 blades in RevSpin's index and their rating counts, the ones
left out for having fewer than 10. Build it with `python -m equipment.build_blades` from `backend/` (web pages are cached in
git-ignored `data/web_cache/`, so a rerun is quick; `--offline` uses only the cache).

**Numbers from RevSpin (ratings only, no review text):** speed, control, stiffness, overall, number of ratings, RevSpin's
approximate US price, and the page URL. They come from one saved copy of RevSpin's blade index (`data/revspin_snapshot/`,
git-ignored, fetched 2026-11-24). Hardness exists for the 3 blade pages saved before the crawl stopped. **RevSpin is not
fetched any more**: it answered our crawler with HTTP 403 (robots.txt allows `/blade/`), so `fetching.py` refuses revspin.net
outright and `revspin.py` only parses saved pages. The owner is asking RevSpin for permission; until then do not crawl it, and see
flag #5 in THIRD_PARTY_LICENSES.md. The site shows "Source: RevSpin" with a link on every blade rating.

**Specs (plies, weight in grams, composition, fibre, handles)** come from the makers and from US stores, and a field is kept only
when a page states it:

| Source | Gives |
| --- | --- |
| Butterfly's blade specification page (butterflyonline.com), one table | plies, weight, material and "Special Structure" (inner fibre), which handle sizes exist. It is the maker's own page and outranks store text. |
| Shopify catalogs (`/products.json`, public): tabletennisstore.us, gotabletennis.com, etabletennis.com, dhssportsusa.com, doublehappinessusa.com, joola.com | handle options, and the same facts where the description states them in words; the product link |
| paddlepalace.com, found through its sitemap as its agent guide asks (`{name}-shakehand-blade`, `-penhold-blade` pages) | handles, the product link, same text facts |

Rules (`blade_specs.py`, tests in `tests/test_blades.py`): names must match exactly after dropping handle codes and "Table Tennis
Blade" ("Hurricane Long 5" is not "Hurricane Long 5 Light"); plies are read from "N+M", "Plies: N" or a lone "N-ply" on a blade with
no fibre layers, never from "N layers"; weight needs a "weight" label and grams; composition needs the blade's own layer
sentence (negations like "without carbon" don't count); a maker's value wins over a store's; stores that disagree leave the field
empty; a penhold listing adds only its handle (it is a different physical blade). `composition` is `wood`, `inner`, `outer` or
`composite` (a fibre layer whose position the page doesn't say), and `fiber` is `alc`, `zlc`, `cnf`, `kevlar`, `glass`, `carbon`
or `other`. Handles are `FL`, `ST`, `AN`, `CS`, `JP` and `PH` (penhold, type not stated). The frontend may flag a blade as carbon
"from the name" (ALC, ZLC, Carbon...) for the beginner rule, but never stores that.

**Politeness** (`fetching.py`): honest User-Agent, robots.txt checked, one request every 2 s, pages cached, a 403 or 401 is final,
a 429 doubles the delay and a host that keeps answering 429 is dropped for the run. Butterfly's US shop (shop.butterflyonline.com)
answered 429 even at 30 s between requests, so its product pages are off by default (`--butterfly-shop` turns them on); the spec
table above doesn't need them.

**Buy links** go to `shared/blade-buy-links.json`, keyed by exact blade name, one link per store, clean URLs (the app adds
affiliate tags). Amazon links are not generated: Amazon shows a bot check to scripts, so a person adds them (see
`docs/amazon_blades_todo.md`). `scripts/check_buy_links.py --blades` rechecks the file.

`frontend/lib/pro-blades.json` maps a pro's blade label to its entry where the exact blade exists (7 of 19 today); the build writes it.

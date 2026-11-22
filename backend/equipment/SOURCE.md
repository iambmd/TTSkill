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

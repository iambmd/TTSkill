"""Rubber recommender: style, rubber type, level and budget in; PingSense rubbers ranked by budget band, then user score."""
from __future__ import annotations

import csv
import json
import math
import sys
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("rubbers.csv")
BUY_LINKS = DATA.resolve().parents[2] / "shared" / "rubber-buy-links.json"

STYLES = ("spin", "speed")
TYPES = ("inverted", "short_pips", "long_pips", "anti_spin")
LEVELS = ("beginner", "intermediate", "advanced")

# Sponge thickness goes down with level: thinner sponge is slower and easier to control.
# Pips and anti-spin play best on thin sponge at every level.
THICKNESS = {
    "inverted": {"advanced": "2.1 mm or max", "intermediate": "1.8-2.0 mm", "beginner": "1.5-1.8 mm"},
    "short_pips": {"advanced": "2.0 mm or max", "intermediate": "1.8-2.0 mm", "beginner": "1.5-1.8 mm"},
    "long_pips": {"advanced": "1.0-1.5 mm", "intermediate": "0.5-1.0 mm", "beginner": "OX (no sponge) to 0.5 mm"},
    "anti_spin": {"advanced": "1.5-2.0 mm", "intermediate": "1.0-1.5 mm", "beginner": "0.5-1.0 mm"},
}

# Per level: the chosen style rating must sit in [lo, hi], and control must reach min_control.
# Beginners get forgiving rubbers, advanced players get the fastest or spinniest.
LEVEL_RULES = {
    "beginner": {"lo": 0.0, "hi": 9.0, "min_control": 8.5},
    "intermediate": {"lo": 8.5, "hi": 9.4, "min_control": 8.0},
    "advanced": {"lo": 9.0, "hi": 10.0, "min_control": 0.0},
}
MIN_OVERALL = 8.0  # skip rubbers reviewers rate poorly, however cheap
BAND = 10.0  # $10 bands counted down from the budget
DEFAULT_BUDGET = 60.0


def _num(v: str) -> float | None:
    v = v.strip().lstrip("$")
    try:
        return float(v)
    except ValueError:
        return None  # "TBD"


def rubber_type(name: str) -> str:
    """The data has no type column; anti-spin rubbers say so in their name."""
    return "anti_spin" if "anti" in name.lower() else "inverted"


@lru_cache(maxsize=1)
def load() -> tuple[dict, ...]:
    with DATA.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return tuple(
        {"name": r["Name"], "brand": r["Brand"], "price": _num(r["Price"]), "speed": _num(r["Speed"]),
         "spin": _num(r["Spin"]), "control": _num(r["Control"]), "hardness": _num(r["Sponge Hardness"]),
         "overall": _num(r["Overall"]), "type": rubber_type(r["Name"])}
        for r in rows
    )


def band(price: float, budget: float) -> int:
    """0 for (budget-10, budget], 1 for (budget-20, budget-10], ... Pricier rubbers are usually
    better, so the band closest to the budget ranks first."""
    return math.floor((budget - price) / BAND + 1e-9)


@lru_cache(maxsize=1)
def buy_links() -> dict[str, list[dict[str, str]]]:
    return json.loads(BUY_LINKS.read_text(encoding="utf-8"))


def recommend(style: str, rtype: str, level: str, budget: float = DEFAULT_BUDGET, limit: int = 8) -> dict:
    """Drop rubbers over budget, then rank by budget band (closest first) and the highest user score (Overall)."""
    if style not in STYLES or rtype not in TYPES or level not in LEVELS:
        raise ValueError("style, rubber type or level not recognised")
    if budget <= 0:
        raise ValueError("budget must be above 0")
    rule = LEVEL_RULES[level]
    picks = []
    for r in load():
        if r["type"] != rtype or r["price"] is None or r["price"] > budget or (r["overall"] or 0) < MIN_OVERALL:
            continue
        if r["control"] is not None and r["control"] < rule["min_control"]:
            continue
        # Anti-spin ratings for speed and spin are all low by design, so style only orders them.
        if rtype != "anti_spin" and not rule["lo"] <= (r[style] or 0) <= rule["hi"]:
            continue
        picks.append(r)
    picks.sort(key=lambda r: (band(r["price"], budget), -(r["overall"] or 0), -(r[style] or 0)))
    note = None
    if rtype in ("short_pips", "long_pips"):
        note = "PingSense has no pips rubbers yet, so there is nothing to rank. They're on the list."
    links = buy_links()
    return {"style": style, "type": rtype, "level": level, "budget": budget, "thickness": THICKNESS[rtype][level],
            "results": [{**r, "buyLinks": links.get(r["name"], [])} for r in picks[:limit]], "note": note}


if __name__ == "__main__" and sys.argv[1:2] == ["--export"]:
    Path(sys.argv[2]).write_text(json.dumps(load(), separators=(",", ":")) + "\n")

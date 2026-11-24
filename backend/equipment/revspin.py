"""Parsers for saved RevSpin blade pages (the index, one blade page). Never fetches: crawling RevSpin is paused
until it gives permission. Keeps numbers and spec facts, never review text."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

BASE = "https://revspin.net/"

# A tag whose quoted attributes may contain ">" (RevSpin's tooltips are HTML inside title="...").
_TAG = re.compile(r"""<(?:[^>"']|"[^"]*"|'[^']*')*>""")


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", fragment)).split())


def _num(value: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(m.group(0)) if m else None


@dataclass
class IndexRow:
    slug: str
    brand: str
    model: str
    speed: float | None
    control: float | None
    stiffness: float | None
    overall: float | None
    price: float | None
    ratings: int

    @property
    def name(self) -> str:
        return self.model if self.brand == "(No Brand)" else f"{self.brand} {self.model}"

    @property
    def url(self) -> str:
        return f"{BASE}blade/{self.slug}.html"


def parse_index(page: str) -> list[IndexRow]:
    """Every blade in the index's brand tables: brand, model, the three headline ratings, overall, price, rating count."""
    rows = []
    pattern = r'<tr>\s*<td class="cell_name"><a href="blade/([^"]+)\.html"[^>]*>\s*<span class="hidden-xs">(.*?)</span>(.*?)</a></td>(.*?)</tr>'
    for slug, brand, model, rest in re.findall(pattern, page, re.S):
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", rest, re.S)]
        if len(cells) < 6:
            continue
        speed, control, stiffness, overall, price, ratings = cells[-6:]
        rows.append(IndexRow(slug, _text(brand), _text(model), _num(speed), _num(control), _num(stiffness),
                             _num(overall), _num(price), int(_num(ratings) or 0)))
    return rows


@dataclass
class BladePage:
    speed: float | None = None
    control: float | None = None
    stiffness: float | None = None
    hardness: float | None = None
    overall: float | None = None
    ratings: int = 0
    price: float | None = None
    weight_g: float | None = None
    plies: int | None = None
    materials: str = ""


def parse_blade(page: str) -> BladePage:
    """User ratings, price and the maker's weight, plies and materials from one saved blade page.
    The review text is never read."""
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S)
    out = BladePage()
    table = re.search(r'id="UserRatingsTable">(.*?)</table>', page, re.S)
    if table:
        for label, cell in re.findall(r'<td class="cell_label[^"]*">(.*?)</td>\s*<td class="cell_rating[^"]*">(.*?)</td>', table.group(1), re.S):
            key = _text(label).lower().split(" ")[0]
            if key in ("speed", "control", "stiffness", "hardness", "overall"):
                # The value is the first number; a word such as "Average" may follow it.
                setattr(out, key, _num(_text(cell)))
    m = re.search(r'itemprop="reviewCount">(\d+)<', page)
    out.ratings = int(m.group(1)) if m else 0
    m = re.search(r'id="actual_price"[^>]*>([\d.,]+)<', page)
    out.price = _num(m.group(1)) if m else None
    details = re.search(r"Manufacturer Details(.*?)</table>", page, re.S)
    if details:
        for label, cell in re.findall(r'<td class="cell_label">(.*?)</td>\s*<td class="cell_rating">(.*?)</td>', details.group(1), re.S):
            key = _text(label).lower().split(" ")[0]
            value = _text(re.sub(r"<!--.*?-->", "", cell, flags=re.S))
            if key == "weight":
                out.weight_g = _num(value)
            elif key == "plies":
                n = _num(value)
                out.plies = int(n) if n else None
            elif key == "materials":
                out.materials = value
    return out

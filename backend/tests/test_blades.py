"""The blade dataset: RevSpin parsers, spec extraction (never guess), the polite fetcher, and the generated files."""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from equipment import blade_specs as bs
from equipment import fetching, revspin

ROOT = Path(__file__).resolve().parents[2]
BLADES = json.loads((ROOT / "backend" / "equipment" / "blades.json").read_text(encoding="utf-8"))

INDEX = """<table><tr class="head"><td class="cell_name">Name</td></tr>
<tr><td class="cell_name"><a href="blade/butterfly-viscaria.html" target="_blank"><span class="hidden-xs">Butterfly</span> Viscaria</a></td>
<td class="cell_char">9.0</td><td class="cell_char cell_even">8.8</td><td class="cell_char">5.2</td>
<td class="cell_overall">9.4</td><td class="cell_price hidden-xs">$185</td><td class="cell_numratings has_ratings">179</td></tr>
<tr><td class="cell_name"><a href="blade/no-brand-alpha-dog.html" target="_blank"><span class="hidden-xs">(No Brand)</span> Alpha Dog</a></td>
<td class="cell_char">-</td><td class="cell_char">-</td><td class="cell_char">-</td>
<td class="cell_overall">-</td><td class="cell_price hidden-xs">$35</td><td class="cell_numratings has_ratings">1</td></tr></table>"""

PAGE = """<table class="ProductRatingTable ratingtable" id="UserRatingsTable">
<tr><td class="cell_label">Speed <img title="<div class='x'>&lt;b&gt;Speed&lt;/b&gt; tip</div>" /></td><td class="cell_rating">9.0</td></tr>
<tr><td class="cell_label">Stiffness <img title="<div>tip</div>" /></td><td class="cell_rating">5.2 &nbsp;<div class="ProductRatingText">Average</div></td></tr>
<tr><td class="cell_label">Hardness</td><td class="cell_rating">5.7</td></tr></table>
<span itemprop="reviewCount">179</span><span id="actual_price" itemprop="price">185</span>
<b>Manufacturer Details</b><table><tr><td class="cell_label">Weight</td><td class="cell_rating">90g</td></tr>
<tr><td class="cell_label">Plies</td><td class="cell_rating">7</td></tr>
<tr><td class="cell_label">Materials</td><td class="cell_rating">5 wood plies; 2 Arylate-carbon</td></tr></table>"""


# ---------------------------------------------------------------- RevSpin parsers

def test_index_rows_split_brand_and_model_and_keep_numbers():
    rows = revspin.parse_index(INDEX)
    assert [(r.brand, r.model, r.name) for r in rows] == [("Butterfly", "Viscaria", "Butterfly Viscaria"), ("(No Brand)", "Alpha Dog", "Alpha Dog")]
    v = rows[0]
    assert (v.speed, v.control, v.stiffness, v.overall, v.price, v.ratings) == (9.0, 8.8, 5.2, 9.4, 185.0, 179)
    assert v.url == "https://revspin.net/blade/butterfly-viscaria.html"
    assert rows[1].speed is None and rows[1].ratings == 1


def test_blade_page_reads_numbers_even_with_html_in_tooltips():
    page = revspin.parse_blade(PAGE)
    assert (page.speed, page.stiffness, page.hardness, page.ratings, page.price) == (9.0, 5.2, 5.7, 179, 185.0)
    assert (page.weight_g, page.plies, page.materials) == (90.0, 7, "5 wood plies; 2 Arylate-carbon")


def test_parsers_never_return_review_text():
    page = PAGE + '<div class="review_text">my secret review words</div>'
    assert "secret" not in repr(revspin.parse_blade(page))


# ---------------------------------------------------------------- specs: only what a page states

@pytest.mark.parametrize("text,plies", [("5+2 ALC inner carbon", 7), ("5W+2ALC", 7), ("5-ply + 2 Super ALC", 7), ("7-ply all-wood blade", 7),
                                        ("Plies: 5", 5), ("5+2H inner-fiber construction", 7), ("great blade", None),
                                        # a lone wood count next to fibre layers, or "layers", is not the total
                                        ("5-ply wood + 2-ply inner arylate-carbon", None),
                                        ("Constructed with 5 layers of premium wood and 2 layers of aryl-carbon fiber", None),
                                        ("Unique 7 plies of high-quality Rosewood", 7)])
def test_plies(text, plies):
    assert bs.plies_of(text) == plies


def test_weight_needs_a_weight_label_and_a_sane_number():
    assert bs.weight_of("Weight range: 85g +/-3g") == 85.0
    assert bs.weight_of("Weight: ~86g") == 86.0
    assert bs.weight_of("85g blade") is None and bs.weight_of("Weight: 9g") is None


def test_composition_from_the_blades_own_layers_only():
    assert bs.parse_text("Built with a 5+2 ALC inner carbon structure.").composition == "inner"
    assert bs.parse_text("5-ply wood + 2 outer carbon layers").composition == "outer"
    assert bs.parse_text("7-ply all-wood blade").composition == "wood"
    assert bs.parse_text("Hurricane Long 5 uses 5+2 ALC layers.").composition == "composite"   # position not stated
    # a rubber or marketing mention is not the blade's construction, and a negation is not a fibre
    assert bs.parse_text("Pairs well with carbon rubbers and ALC blades.").composition is None
    assert bs.parse_text("A weave of composite fibers without carbon, with a koto outer layer wood.").composition is None


def test_handles_come_from_options_in_the_stores_words():
    assert bs.split_handles(["Flared/Straight"]) == ["FL", "ST"]
    assert bs.split_handles(["FL Master", "Chinese Penhold", "Shakehand"]) == ["FL", "CS"]
    assert bs.split_handles(["Flared/Straight/Penhold"]) == ["FL", "ST", "PH"]
    assert bs.parse_text("Handle types: FL (Flared), ST (Straight)").handles == ["FL", "ST"]
    assert bs.split_handles(["Default Title", "Black"]) == []


def test_names_match_exactly_and_a_different_model_never_matches():
    assert bs.compact("Butterfly Viscaria") in bs.name_keys("Viscaria Blade FL", "Butterfly")
    assert bs.compact("Butterfly Fan Zhendong ALC") in bs.name_keys("Butterfly Fan Zhendong ALC CS Table Tennis Blade")
    # "Light" and "Super" are part of the model, not decoration
    assert bs.compact("DHS Hurricane Long 5") not in bs.name_keys('DHS HURRICANE LONG 5 BLADE "LIGHT"', "DHS")
    assert bs.compact("Butterfly Fan Zhendong ALC") not in bs.name_keys("Butterfly Fan Zhendong Super ALC Blade")


def test_sources_that_disagree_leave_the_field_empty():
    a, b = bs.Spec(plies=7, weight=85, handles=["FL"], sources=["a"]), bs.Spec(plies=5, weight=86, handles=["ST"], sources=["b"])
    merged = bs.merge([a, b])
    assert merged.plies is None                       # 7 vs 5: don't pick one
    assert merged.weight == round(85.5)               # within 3 g: the same blade, averaged
    assert merged.handles == ["FL", "ST"] and merged.sources == ["a", "b"]
    assert bs.merge([bs.Spec(plies=7), bs.Spec(plies=7)]).plies == 7


BUTTERFLY = """<table><tr><th>Blade</th><th>Playing Style</th><th>Plies</th><th>Reaction</th><th>Vibration</th><th>Weight (avg. grams)</th>
<th>AN Handle Dims (mm)</th><th>FL Handle Dims (mm)</th><th>ST Handle Dims (mm)</th><th>Material</th><th>Special Structure</th></tr>
<tr><td>Apolonia ZLC Blade</td><td>Offensive</td><td>5-ply + 2 Super ALC</td><td>10.5</td><td>9.5</td><td>89</td><td>100x24</td><td>100x24</td><td></td><td>ZLC (ZL Carbon)</td><td>Innerfiber</td></tr>
<tr><td>Andrzej Grubba Blade</td><td>All-Round</td><td>5-ply</td><td>8.7</td><td>7.8</td><td>85</td><td></td><td>100x25</td><td>100x25</td><td>All Wood</td><td></td></tr></table>"""


def test_butterfly_table_gives_plies_weight_layers_and_which_handles_exist():
    table = bs.parse_butterfly_table(BUTTERFLY, "https://example.test/specs")
    z = table[bs.compact("Butterfly Apolonia ZLC")]
    assert (z.plies, z.weight, z.composition, z.fiber, z.handles) == (7, 89.0, "inner", "zlc", ["FL", "AN"])
    g = table[bs.compact("Butterfly Andrzej Grubba")]
    assert (g.plies, g.composition, g.fiber, g.handles) == (5, "wood", None, ["FL", "ST"])


# ---------------------------------------------------------------- the fetcher

class _Response:
    def __init__(self, text="ok"):
        self.text = text
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self.text.encode()


def _fetcher(tmp_path, monkeypatch, handler):
    monkeypatch.setattr(fetching.time, "sleep", lambda s: None)
    monkeypatch.setattr(fetching, "urlopen", handler)
    return fetching.Fetcher(cache=tmp_path, delay=0)


def test_revspin_is_never_fetched(tmp_path, monkeypatch):
    calls = []
    f = _fetcher(tmp_path, monkeypatch, lambda *a, **k: calls.append(a) or _Response())
    with pytest.raises(fetching.Refused):
        f.get("https://revspin.net/blade/")
    with pytest.raises(fetching.Refused):
        f.get("https://www.revspin.net/blade/x.html")
    assert calls == []


def test_robots_txt_is_respected_and_pages_are_cached(tmp_path, monkeypatch):
    seen = []
    def handler(req, timeout=0):
        seen.append(req.full_url)
        return _Response("User-agent: *\nDisallow: /private/" if req.full_url.endswith("robots.txt") else "page")
    f = _fetcher(tmp_path, monkeypatch, handler)
    assert f.get("https://shop.test/products/a") == "page"
    assert f.get("https://shop.test/products/a") == "page"          # cached: no second request
    assert seen.count("https://shop.test/products/a") == 1
    with pytest.raises(fetching.Refused):
        f.get("https://shop.test/private/x")


def test_a_403_is_final_and_a_429_slows_down_then_stops(tmp_path, monkeypatch):
    def refuse(req, timeout=0):
        if req.full_url.endswith("robots.txt"):
            return _Response("")
        raise urllib.error.HTTPError(req.full_url, 403, "no", {}, None)
    with pytest.raises(fetching.Refused):
        _fetcher(tmp_path, monkeypatch, refuse).get("https://a.test/x")

    attempts = []
    def busy(req, timeout=0):
        if req.full_url.endswith("robots.txt"):
            return _Response("")
        attempts.append(1)
        raise urllib.error.HTTPError(req.full_url, 429, "slow", {"Retry-After": "1"}, None)
    f = _fetcher(tmp_path / "b", monkeypatch, busy)
    with pytest.raises(fetching.Refused):
        f.get("https://b.test/x")
    assert len(attempts) == 5 and f._delay["b.test"] >= 5   # it backed off, and gave up
    with pytest.raises(fetching.Refused):                  # and does not try that host again this run
        f.get("https://b.test/y")
    assert len(attempts) == 5


# ---------------------------------------------------------------- the generated files

FIELDS = {"slug", "name", "brand", "price", "speed", "control", "stiffness", "hardness", "overall", "ratings", "url",
          "plies", "weight", "composition", "fiber", "handles", "specSources"}


def test_the_dataset_is_numbers_and_spec_facts_only():
    assert len(BLADES) > 400
    assert len({b["slug"] for b in BLADES}) == len(BLADES)
    for b in BLADES:
        assert set(b) == FIELDS, b["name"]            # no review text, no summary copied from anywhere
        assert b["ratings"] >= 10 and b["url"] == f"https://revspin.net/blade/{b['slug']}.html"
        assert all(0 < b[k] <= 10 for k in ("speed", "control", "stiffness", "overall")), b["name"]
        assert b["price"] > 0
        assert b["composition"] in (None, "wood", "inner", "outer", "composite")
        assert (b["fiber"] is None) == (b["composition"] in (None, "wood")), b["name"]
        assert set(b["handles"]) <= set(bs.HANDLES)
        assert b["plies"] is None or 1 <= b["plies"] <= 13
        assert b["weight"] is None or 40 <= b["weight"] <= 130
        assert all(u.startswith("https://") and "revspin.net" not in u for u in b["specSources"])


def test_a_stated_spec_has_a_source():
    for b in BLADES:
        if any(b[k] is not None for k in ("plies", "weight", "composition")) or b["handles"]:
            assert b["specSources"], b["name"]


def test_the_frontend_gets_the_same_blades():
    assert json.loads((ROOT / "frontend" / "lib" / "blades.json").read_text(encoding="utf-8")) == BLADES


def test_buy_links_are_us_product_pages_with_no_amazon_yet():
    links = json.loads((ROOT / "shared" / "blade-buy-links.json").read_text(encoding="utf-8"))
    names = {b["name"] for b in BLADES}
    assert links and set(links) <= names
    for name, entries in links.items():
        assert len({e["store"] for e in entries}) == len(entries), name   # one link per store
        for e in entries:
            assert e["type"] in ("official", "retailer") and e["url"].startswith("https://") and "amazon." not in e["url"]
            assert "?" not in e["url"] and "tag=" not in e["url"], e["url"]   # clean URLs; tags are added by the app


def test_skipped_blades_are_listed():
    lines = (ROOT / "backend" / "equipment" / "blades_skipped.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Name,Ratings" and len(lines) > 3000
    assert all(int(line.rsplit(",", 1)[1]) < 10 for line in lines[1:])

"""Rubber recommender: filtering by type and level, price-then-score ranking, thickness advice and the endpoint."""
from fastapi.testclient import TestClient

from app.main import app
from equipment import recommend as rec

client = TestClient(app)


def test_data_loads_from_pingsense_copy():
    rows = rec.load()
    assert len(rows) == 984
    assert {r["type"] for r in rows} == {"inverted", "anti_spin"}


def test_ranked_by_price_band_then_user_score():
    out = rec.recommend("spin", "inverted", "intermediate", limit=20)["results"]
    keys = [(r["price"] // rec.PRICE_BAND, -r["overall"]) for r in out]
    assert keys == sorted(keys)
    assert all(r["overall"] >= rec.MIN_OVERALL for r in out)


def test_level_sets_style_range_and_control():
    for level, rule in rec.LEVEL_RULES.items():
        for r in rec.recommend("speed", "inverted", level, limit=50)["results"]:
            assert rule["lo"] <= r["speed"] <= rule["hi"]
            assert r["control"] is None or r["control"] >= rule["min_control"]


def test_thickness_goes_down_with_level():
    mm = lambda level: rec.recommend("spin", "inverted", level)["thickness"]
    assert (mm("advanced"), mm("intermediate"), mm("beginner")) == ("2.1 mm or max", "1.8-2.0 mm", "1.5-1.8 mm")


def test_anti_spin_and_pips():
    anti = rec.recommend("spin", "anti_spin", "beginner")
    assert anti["results"] and all("anti" in r["name"].lower() for r in anti["results"])
    pips = rec.recommend("spin", "long_pips", "advanced")
    assert pips["results"] == [] and "no pips" in pips["note"]


def test_endpoint():
    res = client.get("/equipment/rubbers", params={"style": "speed", "rubber_type": "inverted", "level": "advanced", "limit": 3})
    assert res.status_code == 200 and len(res.json()["results"]) == 3
    for bad, msg in [({"style": "loop"}, "style"), ({"rubber_type": "pimples"}, "rubber type"), ({"level": "pro"}, "level")]:
        res = client.get("/equipment/rubbers", params=bad)
        assert res.status_code == 400 and msg in res.json()["detail"]

"""Rubber recommender: filtering by type and level, price-then-score ranking, thickness advice and the endpoint."""
from fastapi.testclient import TestClient

from app.main import app
from equipment import recommend as rec

client = TestClient(app)


def test_data_loads_from_pingsense_copy():
    rows = rec.load()
    assert len(rows) == 984
    assert {r["type"] for r in rows} == {"inverted", "anti_spin"}


def test_budget_bands():
    assert [rec.band(p, 50) for p in (50, 45, 40.01, 40, 30.5, 30, 1)] == [0, 0, 0, 1, 1, 2, 4]


def test_within_budget_ranked_by_band_then_user_score():
    out = rec.recommend("spin", "inverted", "intermediate", budget=55, limit=30)["results"]
    assert all(r["price"] <= 55 and r["overall"] >= rec.MIN_OVERALL for r in out)
    keys = [(rec.band(r["price"], 55), -r["overall"]) for r in out]
    assert keys == sorted(keys)
    assert 45 < out[0]["price"] <= 55  # the band closest to the budget leads


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
    res = client.get("/equipment/rubbers", params={"style": "speed", "rubber_type": "inverted", "level": "advanced", "budget": 80, "limit": 3})
    assert res.status_code == 200 and len(res.json()["results"]) == 3
    assert all(r["price"] <= 80 for r in res.json()["results"])
    for bad, msg in [({"style": "loop"}, "style"), ({"rubber_type": "pimples"}, "rubber type"), ({"level": "pro"}, "level"), ({"budget": 0}, "budget")]:
        res = client.get("/equipment/rubbers", params=bad)
        assert res.status_code == 400 and msg in res.json()["detail"]

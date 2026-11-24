"""Find the pros closest to a user: same bat hand, then pros with the user's grip first and a
weighted distance on height and body proportions picks the top 3, then DTW on the chosen
stroke's joint-angle curves says where the user's form differs from each of them."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import numpy as np

from .body import JOINT_NAMES, JOINTS

DATA = Path(__file__).resolve().parents[1] / "data" / "players"
ROSTER = DATA / "players.json"
PROFILES = DATA / "profiles.json"

# Weight of each feature, and the difference that counts as "one unit" (about the spread
# between players), so features with different units are comparable.
WEIGHTS = {"height_cm": 0.4, "arm_span_to_height": 0.2, "leg_to_torso": 0.2,
           "shoulder_width_to_height": 0.1, "stance_width_to_shoulders": 0.1}
SCALE = {"height_cm": 8.0, "arm_span_to_height": 0.04, "leg_to_torso": 0.12,
         "shoulder_width_to_height": 0.02, "stance_width_to_shoulders": 0.35}


def load_pros(roster: Path = ROSTER, profiles: Path = PROFILES) -> list[dict]:
    """Roster entries that have a computed profile, merged with it."""
    players = json.loads(roster.read_text())["players"]
    profs = json.loads(profiles.read_text())["players"] if profiles.exists() else {}
    return [{**p, **profs[p["id"]]} for p in players if p["id"] in profs]


def body_distance(user: dict, pro: dict) -> float:
    """Weighted RMS of scaled differences; height counts only when the user's is known."""
    num = den = 0.0
    for k, w in WEIGHTS.items():
        u = user.get(k)
        v = pro.get("height_cm") if k == "height_cm" else pro.get("body", {}).get(k)
        if u is None or v is None:
            continue
        num += w * ((u - v) / SCALE[k]) ** 2
        den += w
    return math.sqrt(num / den) if den else float("inf")


def similarity(d: float) -> int:
    return int(round(100 * math.exp(-0.5 * d))) if math.isfinite(d) else 0


def dtw(a: list[float], b: list[float], band: int = 8) -> tuple[float, list[tuple[int, int]]]:
    """Dynamic time warping with a Sakoe-Chiba band. The timing is aligned on the curves'
    shapes (mean removed), so a constant offset - say an elbow 20 degrees straighter all the
    way through - is measured, not warped away. Returns (mean |diff| along the path, path)."""
    raw_x, raw_y = np.asarray(a, float), np.asarray(b, float)
    x, y = raw_x - raw_x.mean(), raw_y - raw_y.mean()
    n, m = len(x), len(y)
    band = max(band, abs(n - m))
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(1, i - band), min(m, i + band) + 1):
            cost[i, j] = abs(x[i - 1] - y[j - 1]) + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        step = int(np.argmin([cost[i - 1, j - 1], cost[i - 1, j], cost[i, j - 1]]))
        i, j = (i - 1, j - 1) if step == 0 else (i - 1, j) if step == 1 else (i, j - 1)
    path.reverse()
    return float(np.mean([abs(raw_x[p] - raw_y[q]) for p, q in path])), path


def _phase(i: int, contact: int) -> str:
    return "the backswing" if i < contact - 3 else "contact" if i <= contact + 3 else "the finish"


def _note(joint: str, diff: float, phase: str, pro: str, lang: str = "en") -> str:
    import i18n

    w = i18n.MATCH[i18n.norm(lang)]
    what = w["what"][joint]
    verb = "are" if what in ("legs", "shoulders") else "is"
    return w["note"].format(what=what, verb=verb, deg=f"{abs(diff):.0f}°", pro=pro, phase=w["phase"][phase],
                            direction=(w["more"] if diff > 0 else w["less"])[joint])


def form_compare(user: dict, pro: dict, pro_name: str, lang: str = "en") -> dict:
    """Compare two angle-curve dicts (body.angle_curves). Lower differences = closer form.
    lang: the language of the notes."""
    joints, notes = {}, []
    uc = int(user.get("contact_index", 20))
    for j in JOINTS:
        if j not in user or j not in pro:
            continue
        mean_abs, path = dtw(user[j], pro[j])
        by_phase: dict[str, list[float]] = {}
        for p, q in path:
            by_phase.setdefault(_phase(p, uc), []).append(user[j][p] - pro[j][q])
        phase, diffs = max(by_phase.items(), key=lambda kv: abs(np.mean(kv[1])))
        joints[j] = {"mean_diff_deg": round(mean_abs, 1), "worst_phase": phase,
                     "signed_diff_deg": round(float(np.mean(diffs)), 1)}
    for j, info in sorted(joints.items(), key=lambda kv: -abs(kv[1]["signed_diff_deg"]))[:2]:
        if abs(info["signed_diff_deg"]) >= 8:
            notes.append(_note(j, info["signed_diff_deg"], info["worst_phase"], pro_name, lang))
    avg = float(np.mean([v["mean_diff_deg"] for v in joints.values()])) if joints else 90.0
    return {"score": int(round(100 * math.exp(-avg / 25))), "joints": joints, "notes": notes,
            "joint_names": {j: JOINT_NAMES[j] for j in joints}}


def warnings(pro: dict, user_grip: Optional[str] = None, lang: str = "en") -> list[str]:
    """Why copying part of this pro's technique needs care: their equipment_notes (e.g. an
    anti-spin backhand), and penhold, whose backhand differs from shakehand. A penhold user
    doesn't need the penhold note. lang: their language (equipment notes in i18n.py)."""
    import i18n

    lang = i18n.norm(lang)
    out = []
    if pro.get("equipment_notes"):
        out.append(i18n.EQUIPMENT_NOTES_VI.get(pro.get("id"), pro["equipment_notes"]) if lang == "vi"
                   else pro["equipment_notes"])
    if pro.get("grip") == "penhold" and user_grip != "penhold":
        out.append(i18n.MATCH[lang]["penhold"].format(name=pro["name"]))
    return out


def match(user_body: dict, user_curves: Optional[dict], stroke: str, bat_hand: str,
          pros: Optional[list[dict]] = None, top: int = 3, grip: Optional[str] = None,
          lang: str = "en") -> list[dict]:
    """user_body: body.body_ratios() plus optional height_cm. grip: the user's grip, when they
    gave it; pros with the same grip rank first, others only fill the list. Returns the top
    pros, best first."""
    pros = load_pros() if pros is None else pros
    same_hand = [p for p in pros if p["bat_hand"] == bat_hand] or pros
    ranked = sorted(same_hand, key=lambda p: (grip is not None and p.get("grip", "shakehand") != grip,
                                              body_distance(user_body, p)))[:top]
    out = []
    for p in ranked:
        d = body_distance(user_body, p)
        clips = [c for c in p.get("strokes", {}).get(stroke, []) if c.get("curves")]
        forms = [(form_compare(user_curves, c["curves"], p["name"], lang), c) for c in clips] if user_curves else []
        form, clip = max(forms, key=lambda fc: fc[0]["score"]) if forms else (None, clips[0] if clips else None)
        out.append({
            "id": p["id"], "name": p["name"], "country": p.get("country"), "gender": p.get("gender"),
            "height_cm": p["height_cm"], "bat_hand": p["bat_hand"], "grip": p.get("grip", "shakehand"),
            "warnings": warnings(p, grip, lang),
            "score": similarity(d), "body_distance": round(d, 2),
            "form_score": form["score"] if form else None,
            "differences": form["notes"] if form else [],
            "form": form, "breakdown": clip.get("breakdown") if clip else None,
            "source_url": clip.get("url") if clip else None,
        })
    return out

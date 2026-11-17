"""Interval metrics for rally detection: matching, precision/recall, merge/split counts."""
from __future__ import annotations


def iou(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def in_spans(t: float, spans: list[tuple[float, float]], margin: float = 0.0) -> bool:
    return any(s - margin <= t <= e + margin for s, e in spans)


def match_rallies(detected: list[tuple[float, float]], truth: list[tuple[float, float]],
                  min_iou: float = 0.5) -> dict:
    """Greedy one-to-one matching by IoU, plus the failure counts the bugs are about:
    merges (one detection covering several true rallies), splits (one true rally covered
    by several detections) and false rallies (detections that barely touch real play)."""
    pairs: list[tuple[float, int, int]] = sorted(
        ((iou(d, t), i, j) for i, d in enumerate(detected) for j, t in enumerate(truth)),
        reverse=True)
    used_d: set[int] = set()
    used_t: set[int] = set()
    matched = []
    for score, i, j in pairs:
        if score < min_iou or i in used_d or j in used_t:
            continue
        used_d.add(i)
        used_t.add(j)
        matched.append((i, j, round(score, 3)))
    merges = sum(
        1 for d in detected
        if sum(1 for t in truth if overlap(d, t) >= 0.5 * (t[1] - t[0])) >= 2)
    splits = sum(
        1 for t in truth
        if sum(1 for d in detected if overlap(d, t) >= 0.6 * (d[1] - d[0])) >= 2)
    false_rallies = sum(
        1 for d in detected
        if sum(overlap(d, t) for t in truth) < 0.2 * (d[1] - d[0]))
    n_d, n_t = len(detected), len(truth)
    precision = len(matched) / n_d if n_d else 0.0
    recall = len(matched) / n_t if n_t else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"detected": n_d, "truth": n_t, "matched": len(matched),
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "merges": merges, "splits": splits, "false_rallies": false_rallies,
            "pairs": matched}


def onset_play_split(onsets: list[float], play: list[tuple[float, float]],
                     prep: list[tuple[float, float]], margin: float = 0.3) -> dict:
    """How many detected onsets fall in real play vs serve-prep vs dead time."""
    n_play = sum(1 for t in onsets if in_spans(t, play, margin))
    n_prep = sum(1 for t in onsets if not in_spans(t, play, margin) and in_spans(t, prep))
    n_dead = len(onsets) - n_play - n_prep
    total = len(onsets) or 1
    return {"onsets": len(onsets), "in_play": n_play, "in_prep": n_prep, "in_dead": n_dead,
            "play_precision": round(n_play / total, 3)}

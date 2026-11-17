"""Score a saved pose track on manually reviewed identity frames, including abstentions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from technique.pose import PoseTrack, load_track


def audit(track: PoseTrack, labels: dict) -> dict:
    rows = []
    for label in labels['frames']:
        i = int(np.argmin(abs(track.times - label['time'])))
        if abs(track.times[i] - label['time']) > .25:
            raise ValueError('track sampling is too sparse for the audit')
        result = 'abstained'
        if track.valid[i]:
            x, y = track.lm[i, [23,24], :2].mean(0)
            left, top, right, bottom = label['box']
            result = 'correct' if left <= x <= right and top <= y <= bottom else 'wrong'
        rows.append({'time': label['time'], 'result': result})
    return {'correct': sum(r['result'] == 'correct' for r in rows),
            'wrong': sum(r['result'] == 'wrong' for r in rows),
            'abstained': sum(r['result'] == 'abstained' for r in rows),
            'sampled_visibility': float(track.valid.mean()), 'frames': rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--track', type=Path, required=True)
    ap.add_argument('--labels', type=Path, default=Path(__file__).parent/'regressions/match_b_identity.json')
    args = ap.parse_args()
    print(json.dumps(audit(load_track(args.track), json.loads(args.labels.read_text())), indent=2))


if __name__ == '__main__':
    main()

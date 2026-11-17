"""Score a frozen wing experiment on cached, visually labelled contact windows."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from technique import pose, strokes
from . import geometry


def score(directory: Path) -> dict:
    manifest = json.loads((directory / 'manifest.json').read_text())
    rows = []
    for row in manifest['contacts']:
        track = pose.load_track(directory / row['track'])
        features = strokes.features(track, row['hand'], row['contact_i'])
        baseline = 'forehand' if features['side_score'] > .15 else 'backhand'
        evidence = geometry.evidence(track, row['hand'], row['contact_i'])
        rows.append({**row, 'baseline': baseline, 'candidate': evidence['wing'],
                     'hybrid': evidence['wing'] or baseline, 'evidence': evidence})
    decisions = [r for r in rows if r['candidate']]
    summary = {'n': len(rows), 'decisions': len(decisions),
               'selective_correct': sum(r['candidate'] == r['wing'] for r in decisions),
               'selective_precision': (sum(r['candidate'] == r['wing'] for r in decisions)
                                       / len(decisions) if decisions else None)}
    for model in ('baseline', 'hybrid'):
        matrix = {true: {pred: sum(r['wing'] == true and r[model] == pred for r in rows)
                         for pred in ('forehand', 'backhand')}
                  for true in ('forehand', 'backhand')}
        summary[model] = {'correct': sum(r[model] == r['wing'] for r in rows),
                          'confusion': matrix,
                          'recall': {w: matrix[w][w] / sum(matrix[w].values())
                                     if sum(matrix[w].values()) else None for w in matrix}}
    return {'video': manifest['video'], 'split': manifest['split'],
            'video_sha256': manifest['video_sha256'], 'labels_sha256': manifest['labels_sha256'],
            'scope': manifest['scope'], 'summary': summary, 'contacts': rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directories', type=Path, nargs='+')
    ap.add_argument('--freeze', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    freeze = json.loads(args.freeze.read_text())
    digest = hashlib.sha256(Path(geometry.__file__).read_bytes()).hexdigest()
    if digest != freeze['geometry_sha256']:
        raise ValueError('candidate changed since freeze; do not call this a frozen validation')
    reports = [score(directory) for directory in args.directories]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({'freeze': freeze, 'reports': reports}, indent=2))
    for report in reports:
        print(json.dumps({key: report[key] for key in ('video', 'split', 'summary')}))


if __name__ == '__main__':
    main()

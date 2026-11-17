"""Cache pose windows at labelled visual contacts for separate calibration and validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from technique import media, pose


def extract(video: Path, labels_path: Path, out: Path, hands: dict[str, str], split: str) -> None:
    info = media.probe(video)
    labels = json.loads(labels_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for frame, label in sorted(labels.items(), key=lambda x: int(x[0])):
        parts = label.split()[0].split('_')
        if len(parts) != 3 or parts[1] not in ('forehand', 'backhand') or parts[2] in ('serve', 'lob'):
            continue
        table_side, wing, kind = parts
        t = int(frame) / info['fps']
        start = max(0, t - .6)
        track_path = out / f'{frame}.npz'
        if not track_path.exists():
            clip = out / 'contact.mp4'
            x = 0 if table_side == 'left' else info['width'] // 2
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-i', str(video),
                            '-t', '1.2', '-vf', f'crop=iw/2:ih:{x}:0,scale=-2:720,fps=30',
                            '-an', str(clip)], check=True)
            try:
                track = pose.extract_pose(clip)
                pose.save_track(track, track_path)
            finally:
                clip.unlink(missing_ok=True)
        track = pose.load_track(track_path)
        row = {'frame': int(frame), 'table_side': table_side, 'hand': hands[table_side],
               'wing': wing, 'subtype': kind, 'track': track_path.name,
               'contact_i': round((t - start) * track.fps), 'visibility': float(track.valid.mean())}
        rows.append(row)
        print(video.stem, row, flush=True)
    with video.open('rb') as source:
        video_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    (out / 'manifest.json').write_text(json.dumps({
        'video': video.name, 'video_sha256': video_hash,
        'labels_sha256': hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        'fps': info['fps'], 'split': split, 'hands': hands,
        'license': 'CC BY-NC-SA-4.0', 'source_url': 'https://lab.osai.ai/',
        'annotation_url': 'https://github.com/moamal01/table_tennis_data',
        'scope': 'visual wing classification conditional on labelled player/contact and verified hand; not audio',
        'contacts': rows,
    }, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video', type=Path, required=True)
    ap.add_argument('--labels', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--split', choices=('calibration', 'validation'), required=True)
    ap.add_argument('--left-hand', choices=('left', 'right'), required=True)
    ap.add_argument('--right-hand', choices=('left', 'right'), required=True)
    args = ap.parse_args()
    extract(args.video, args.labels, args.out,
            {'left': args.left_hand, 'right': args.right_hand}, args.split)


if __name__ == '__main__':
    main()

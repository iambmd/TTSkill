"""Extract local DTW wing templates from licensed Extended OpenTTGames visual annotations."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from technique import pose, temporal


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video', type=Path, required=True)
    ap.add_argument('--labels', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--left-hand', choices=['left', 'right'], required=True, help='visually verified hand of table-left player')
    ap.add_argument('--right-hand', choices=['left', 'right'], required=True, help='visually verified hand of table-right player')
    ap.add_argument('--max-per-wing', type=int, default=10)
    args = ap.parse_args()
    info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(args.video)],
                                    check=True, capture_output=True, text=True).stdout)
    stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
    numerator, denominator = map(int, stream['r_frame_rate'].split('/'))
    fps = numerator / denominator
    with args.video.open('rb') as source:
        video_sha256 = hashlib.file_digest(source, 'sha256').hexdigest()
    labels = json.loads(args.labels.read_text())
    selected = {'forehand': 0, 'backhand': 0}
    templates = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        for frame, label in sorted(labels.items(), key=lambda x: int(x[0])):
            parts = label.split()[0].split('_')
            if len(parts) != 3 or parts[1] not in selected or parts[2] in ('serve', 'lob'):
                continue
            table_side, wing, kind = parts
            if selected[wing] >= args.max_per_wing:
                continue
            t = int(frame) / fps
            clip = Path(tmp) / 'swing.mp4'
            # Label prefixes are table sides, never anatomical handedness.
            x = 0 if table_side == 'left' else stream['width'] // 2
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(max(0, t-.5)), '-i', str(args.video),
                            '-t', '1', '-vf', f"crop=iw/2:ih:{x}:0,scale=-2:720,fps=30", '-an', str(clip)], check=True)
            tr = pose.extract_pose(clip)
            hand = args.left_hand if table_side == 'left' else args.right_hand
            seq = temporal.sequence(tr, hand, 15)
            if seq is None:
                continue
            templates.append({'wing': wing, 'stroke': kind, 'frame': int(frame), 'table_side': table_side,
                              'hand_verified': hand, 'sequence': seq.tolist()})
            selected[wing] += 1
            print(frame, label.split()[0], hand, selected, flush=True)
    args.output.write_text(json.dumps({'version': 1, 'source': str(args.video),
        'video_sha256': video_sha256, 'fps': fps,
        'source_url': 'https://lab.osai.ai/',
        'annotation_url': 'https://github.com/moamal01/table_tennis_data',
        'license': 'CC BY-NC-SA-4.0', 'purpose': 'local visual development; NOT audio training',
        'labels_sha256': hashlib.sha256(args.labels.read_bytes()).hexdigest(),
        'templates': templates}, indent=2))
    print('wrote', args.output, selected)


if __name__ == '__main__':
    main()

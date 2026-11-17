"""Rerun the four existing demo inputs and export only verified results to the frontend."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app import jobs, pipelines

KINDS = ('autocut', 'breakdown', 'match', 'coach')
REQUEST = "Here's my match, show my best rallies and fix my forehand"


def probe(path: Path) -> dict:
    return json.loads(subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True).stdout)


def public_video(source: Path, dest: Path) -> tuple[str, float]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-map', '0:v:0', '-map', '0:a?',
                    '-vf', "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                    '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-movflags', '+faststart', str(dest)], check=True)
    info = probe(dest)
    stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
    assert stream['codec_name'] == 'h264' and stream['pix_fmt'] == 'yuv420p'
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()[:12]
    url = '/' + dest.relative_to(ROOT / 'frontend/public').as_posix()
    return f'{url}?v={digest}', round(float(info['format']['duration']), 1)


def run(kind: str, manifest: Path) -> None:
    # Demo refreshes use local templates; never upload video frames or load credentials.
    os.environ['ANTHROPIC_API_KEY'] = ''
    video = ROOT / f'frontend/public/examples/{kind}-before.mp4'
    params = {'video': video.name}
    if kind == 'autocut':
        params.update(mode='highlights', top_n=4, threshold=3.0, gap=1.6, min_hits=4)
    elif kind == 'breakdown':
        params.update(stroke='', stroke_type='auto', player='Ma Long', hand='auto')
    elif kind == 'match':
        params.update(stroke='forehand', hand='auto', grip='shakehand', height_cm=None)
    else:
        params['request'] = REQUEST
    job = jobs.create(kind, params)
    state = json.loads(manifest.read_text()) if manifest.exists() else {}
    state[kind] = {'job_id': job['id'], 'source_sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
                   'revision': subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,text=True,cwd=ROOT).stdout.strip(),
                   'generated_at': datetime.now(ZoneInfo('America/New_York')).isoformat()}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(state, indent=2))
    print(f'{kind}: job {job["id"]}', flush=True)
    if kind == 'autocut':
        jobs.run(pipelines.run_autocut, job['id'], video, 'highlights', 4, 3., 1.6, 4)
    elif kind == 'breakdown':
        jobs.run(pipelines.run_breakdown, job['id'], video, '', '', 'Ma Long', 'auto', '')
    elif kind == 'match':
        jobs.run(pipelines.run_match, job['id'], video, 'forehand', None, 'auto', 'shakehand')
    else:
        from agent.coach import run_coach
        jobs.run(run_coach, job['id'], video, None, REQUEST)
    result = jobs.load(job['id'])
    print(kind, result['status'], result['message'], flush=True)
    if result['status'] != 'done':
        raise RuntimeError(result['message'])
    if kind == 'coach':
        assert {'highlights','breakdown'} <= {o['kind'] for o in result.get('outputs',[])}, result.get('summary')
        assert 'Some steps failed:' not in result.get('summary',''), result['summary']
    else:
        assert result.get('resultUrl') and (jobs.job_dir(job['id'])/'result.mp4').exists()


def export(manifest: Path) -> None:
    state = json.loads(manifest.read_text())
    records, assets = {}, {}
    # Validate every completed job before replacing any public asset.
    for kind in KINDS:
        job = jobs.load(state[kind]['job_id'])
        if not job or job['status'] != 'done':
            raise RuntimeError(f'{kind} has no successful fresh run')
        if kind == 'coach':
            assert {'highlights','breakdown'} <= {o['kind'] for o in job.get('outputs',[])}
        else:
            assert (jobs.job_dir(job['id'])/'result.mp4').is_file()
        records[kind] = job
    for kind, job in records.items():
        original_id = job['id']
        job['id'] = f'demo-{kind}'
        job['demoRefresh'] = state[kind]
        assets[kind] = {'generatedAt': state[kind]['generated_at']}
        if kind == 'coach':
            outputs = []
            for output in job['outputs']:
                source = jobs.job_dir(original_id) / output['url'].rsplit('/',1)[-1]
                url, seconds = public_video(source, ROOT / f'frontend/public/examples/coach-after-{output["kind"]}.mp4')
                outputs.append({**output, 'url': url})
                assets[kind][output['kind']] = {'url': url, 'duration': seconds}
            job['outputs'] = outputs
            # Static coach outputs are the cached results; no backend file URLs remain.
            job['resultUrl'] = None
        else:
            url, seconds = public_video(jobs.job_dir(original_id)/'result.mp4', ROOT / f'frontend/public/examples/{kind}-after.mp4')
            job['resultUrl'] = url
            assets[kind].update(url=url, duration=seconds)
        # Internal agent files may contain absolute paths and are not needed by the demo.
        job.pop('agentFiles', None)
    # Keep existing bookmarked video URLs current too.
    for kind, legacy in (('breakdown', 'breakdown'), ('autocut', 'highlights')):
        shutil.copyfile(ROOT / f'frontend/public/examples/{kind}-after.mp4',
                        ROOT / f'frontend/public/demo/{legacy}.mp4')
    dest = ROOT / 'frontend/lib'
    (dest/'demo-jobs.json').write_text(json.dumps({j['id']: j for j in records.values()}, indent=2)+'\n')
    coach = records['coach']
    (dest/'coach-example.json').write_text(json.dumps({k:coach[k] for k in ('todos','summary','outputs','engine')},indent=2)+'\n')
    (dest/'demo-assets.json').write_text(json.dumps(assets,indent=2)+'\n')
    print('Exported four fresh demo jobs and five result videos.', flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kind', choices=KINDS)
    ap.add_argument('--export', action='store_true')
    ap.add_argument('--manifest', type=Path, default=ROOT/'backend/data/demo-refresh/manifest.json')
    args = ap.parse_args()
    if args.kind:
        run(args.kind, args.manifest)
    elif args.export:
        export(args.manifest)
    else:
        ap.error('choose --kind or --export')


if __name__ == '__main__':
    main()

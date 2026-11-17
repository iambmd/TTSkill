"""Exercise the two production rally callers on the known crossfade sequence."""
from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import tempfile


def main() -> None:
    # This smoke test uses the local fixed plan and never sends frames to an analyzer.
    os.environ['ANTHROPIC_API_KEY'] = ''
    from fastapi.testclient import TestClient
    from app.main import app

    source = Path(__file__).resolve().parents[2] / 'samples' / 'coaching-demo.mp4'
    results = {}
    with tempfile.TemporaryDirectory(prefix='ttskill-smoke-') as folder:
        video = Path(folder) / 'montage.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '26', '-i', str(source), '-t', '27',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', str(video)], check=True)
        with TestClient(app) as client:
            for kind, form in (
                ('autocut', {'mode': 'highlights', 'top_n': '4', 'threshold': '3', 'gap': '1.6', 'min_hits': '4'}),
                ('coach', {'request': 'Cut my best rallies'}),
            ):
                with video.open('rb') as stream:
                    response = client.post('/jobs/' + kind, data=form, files={'video': ('montage.mp4', stream, 'video/mp4')})
                assert response.status_code == 201, response.text
                job = client.get('/jobs/' + response.json()['id']).json()
                assert job['status'] == 'done', job
                url = job['resultUrl'] if kind == 'autocut' else job['outputs'][0]['url']
                ranged = client.get(url, headers={'Range': 'bytes=0-1023'})
                assert ranged.status_code == 206 and len(ranged.content) == 1024, ranged.status_code
                assert ranged.headers['content-type'] == 'video/mp4'
                if kind == 'autocut':
                    assert len(job['rallies']) == 4, job['rallies']
                    assert max(r['end']-r['start'] for r in job['rallies']) < 10, job['rallies']
                else:
                    assert job['engine'] == 'fallback'
                    assert 'Some steps failed:' not in job['summary']
                results[kind] = {k:job.get(k) for k in ('id', 'message', 'rallies', 'summary', 'outputs')}
    report = Path(__file__).parent / 'work' / 'milestone2-smoke.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

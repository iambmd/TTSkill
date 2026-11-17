"""Reproduce an identity audit with the current selector or a revision-local snapshot."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from typing import Iterator

from technique import pose
from .audit_player import audit


@contextmanager
def snapshot(revision: str | None) -> Iterator[types.ModuleType]:
    if revision is None:
        yield pose
        return
    with tempfile.TemporaryDirectory(prefix='ttskill-identity-') as folder:
        name = '_identity_' + Path(folder).name.replace('-', '_')
        package = types.ModuleType(name)
        package.__path__ = [folder]
        sys.modules[name] = package
        try:
            for module in ('pose', 'identity'):
                source = subprocess.run(['git', 'show', f'{revision}:backend/technique/{module}.py'],
                                        check=True, capture_output=True, text=True).stdout
                (Path(folder) / f'{module}.py').write_text(source)
            yield importlib.import_module(name + '.pose')
        finally:
            for module in list(sys.modules):
                if module == name or module.startswith(name + '.'):
                    del sys.modules[module]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video', type=Path, required=True)
    ap.add_argument('--labels', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--baseline')
    ap.add_argument('--stride', type=int, default=12)
    args = ap.parse_args()
    if args.stride < 1:
        ap.error('--stride must be positive')
    args.out.mkdir(parents=True, exist_ok=True)
    with snapshot(args.baseline) as module:
        reference = module.initial_identity(args.video)
        track = module.extract_pose(args.video, stride=args.stride, identity=reference)
        module.save_track(track, args.out / 'track.npz')
    result = audit(track, json.loads(args.labels.read_text()))
    with args.video.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    result.update(video_sha256=digest, labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
                  revision=args.baseline or 'working tree', stride=args.stride)
    (args.out / 'audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

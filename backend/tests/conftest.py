"""Small real media files, made once per run with ffmpeg, for tests that need the upload
checks (backend/app/validate.py) to pass or fail for a real reason."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# Jobs run inside the API in tests (FastAPI background tasks), as before the worker; the queue
# and worker tests switch this off themselves.
os.environ.setdefault("TTSKILL_INLINE", "1")


def make_media(path: Path, seconds: float = 3.0, size: str = "640x360", video: bool = True,
               audio: bool = True) -> Path:
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if video:
        cmd += ["-f", "lavfi", "-i", f"testsrc=size={size}:rate=30:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=3000:duration={seconds}"]
    if video:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast"]
    if audio:
        cmd += ["-c:a", "aac"]
    subprocess.run([*cmd, "-shortest", str(path)], check=True)
    return path


@pytest.fixture(scope="session")
def media(tmp_path_factory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("media")
    return {
        "ok": make_media(d / "ok.mp4"),
        "short": make_media(d / "short.mp4", seconds=1.0),
        "tiny": make_media(d / "tiny.mp4", size="320x180"),
        "sound_only": make_media(d / "sound_only.mp4", video=False),
    }


@pytest.fixture
def upload(media):
    """files= for TestClient: a valid 3 s 640x360 clip, or another of `media` by name."""
    def files(name: str = "ok", filename: str = "clip.mp4") -> dict:
        return {"video": (filename, media[name].read_bytes(), "video/mp4")}
    return files

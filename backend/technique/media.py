"""ffmpeg helpers: probing, proxy transcode, frame grabbing, final encode."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH")
    return exe


def probe(path: str | Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name:format=duration",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    st = data["streams"][0]
    num, den = st.get("r_frame_rate", "30/1").split("/")
    return {
        "width": int(st["width"]),
        "height": int(st["height"]),
        "fps": float(num) / float(den or 1),
        "codec": st.get("codec_name"),
        "duration": float(data["format"]["duration"]),
    }


def make_proxy(src: str | Path, dst: str | Path, height: int = 720, fps: int = 30,
               start: float | None = None, end: float | None = None) -> Path:
    """Transcode to H.264 at <=`height`p constant fps so OpenCV can read it reliably
    (iPhone HEVC .MOV files often fail in OpenCV). Optionally trims [start, end]."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ffmpeg(), "-y", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if end is not None:
        cmd += ["-t", f"{end - (start or 0):.3f}"]
    cmd += [
        "-vf", f"scale=-2:'min({height},ih)',fps={fps}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-an", str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst


def encode_frames(frame_iter, dst: str | Path, width: int, height: int, fps: int = 30) -> Path:
    """Pipe raw BGR frames into ffmpeg -> H.264 mp4."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            _ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(dst),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    try:
        for frame in frame_iter:
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg encode failed ({proc.returncode})")
    return dst

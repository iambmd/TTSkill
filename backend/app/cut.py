"""Cut detected rallies out of a match video and join them into one MP4."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

PAD_S = 1.5  # keep a little lead-in (serve toss) and tail after the last hit


def duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def padded_segments(spans: list[tuple[float, float]], total: float, pad: float = PAD_S,
                    merge: bool = True) -> list[tuple[float, float]]:
    """Pads each (start, end) span, clamps to [0, total] and, when `merge`, joins overlapping
    spans (input must then be chronological)."""
    segs = [(max(0.0, s - pad), min(total, e + pad)) for s, e in spans]
    if not merge:
        return segs
    out: list[tuple[float, float]] = []
    for s, e in segs:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def cut_and_concat(video: Path, segments: list[tuple[float, float]], workdir: Path, dest: Path,
                   progress: Callable[[float], None] | None = None) -> Path:
    """Re-encodes each segment with identical settings (frame-accurate cuts, normalised streams
    so iPhone HEVC/variable-rate input concatenates cleanly) and joins them without re-encoding."""
    parts_dir = workdir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for i, (s, e) in enumerate(segments):
        part = parts_dir / f"part{i:03d}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-i", str(video), "-t", f"{e - s:.3f}",
             "-map", "0:v:0", "-map", "0:a:0?",
             "-vf", "scale=-2:'min(720,ih)',fps=30", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
             str(part)],
            check=True,
        )
        parts.append(part)
        if progress:
            progress((i + 1) / len(segments))
    listing = parts_dir / "list.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", "-movflags", "+faststart", str(dest)],
        check=True,
    )
    return dest

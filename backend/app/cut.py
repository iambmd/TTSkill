"""Cut detected rallies out of a match video and join them into one MP4."""
from __future__ import annotations

import subprocess
from tempfile import NamedTemporaryFile
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
                    merge: bool = True,
                    bounds: list[tuple[float, float]] | None = None) -> list[tuple[float, float]]:
    """Pads each (start, end) span, clamps to [0, total] and, when `merge`, joins overlapping
    spans (input must then be chronological)."""
    limits = bounds if bounds is not None else [(0.0, total)] * len(spans)
    # Padding must not pull a neighbouring montage clip back into a split rally.
    segs = [(max(0.0, lo, s - pad), min(total, hi, e + pad))
            for (s, e), (lo, hi) in zip(spans, limits, strict=True)]
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
                   progress: Callable[[float], None] | None = None, *,
                   clip_ready: Callable[[int, int, Path], None] | None = None) -> Path:
    """Re-encodes each segment with identical settings (frame-accurate cuts, normalised streams
    so iPhone HEVC/variable-rate input concatenates cleanly) and joins them without re-encoding."""
    parts_dir = workdir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for i, segment in enumerate(segments):
        part = cut_segment(video, segment, parts_dir / f"part{i:03d}.mp4")
        parts.append(part)
        if clip_ready:
            clip_ready(i + 1, len(segments), part)
        if progress:
            progress((i + 1) / len(segments))
    return concat_parts(parts, dest)


def cut_segment(video: Path, segment: tuple[float, float], part: Path) -> Path:
    s, e = segment
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-i", str(video), "-t", f"{e - s:.3f}",
         "-map", "0:v:0", "-map", "0:a:0?",
         "-vf", "scale=-2:'min(720,ih)',fps=30", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         str(part)],
        check=True,
    )
    return part


def concat_parts(parts: list[Path], dest: Path) -> Path:
    """Join normalized clips from one folder in the order given."""
    with NamedTemporaryFile(mode="w", suffix=".txt", dir=parts[0].parent, delete=False) as f:
        f.write("".join(f"file '{part.name}'\n" for part in parts))
        listing = Path(f.name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-i", str(listing),
             "-c", "copy", "-movflags", "+faststart", str(dest)],
            check=True,
        )
    finally:
        listing.unlink(missing_ok=True)
    return dest


def thumbnail(clip: Path, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-frames:v", "1", "-vf", "scale=320:-2",
         "-update", "1", str(dest)],
        check=True,
    )

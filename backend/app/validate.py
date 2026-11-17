"""Input checks for the API endpoints, against the limits in shared/limits.json.

Each check raises Invalid with a message the user can act on; main.py answers it with a
422. The forms run the same checks first (frontend/lib/validate.ts), so these mostly catch
API callers and what only the server can see: a file's duration, tracks and resolution."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from limits import LIMITS


class Invalid(ValueError):
    """Bad input. The message is shown to the user as-is."""


_NUMBER = re.compile(r"[0-9]+(\.[0-9]+)?")  # ASCII only, like the form's check


def _or(options: list[str]) -> str:
    return ", ".join(options[:-1]) + f" or {options[-1]}" if len(options) > 1 else options[0]


def _num(v: float) -> str:
    return f"{v:g}"


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def choice(value: str, key: str, label: str) -> str:
    """value must be one of LIMITS["choices"][key] (the options the form offers)."""
    if value not in LIMITS["choices"][key]:
        raise Invalid(f"{label} must be {_or(LIMITS['choices'][key])}.")
    return value


def in_range(value: float, key: str, label: str) -> float:
    """An Auto-Cut setting within LIMITS["autocut"][key]. NaN fails the comparison too."""
    lo, hi = LIMITS["autocut"][key]["min"], LIMITS["autocut"][key]["max"]
    if not lo <= value <= hi:
        raise Invalid(f"{label} must be between {_num(lo)} and {_num(hi)}.")
    return value


def height_cm(raw: str) -> float | None:
    """Optional height in cm. Plain digits only, so text, negatives, hex and exponents fail."""
    raw = raw.strip()
    if not raw:
        return None
    lo, hi = LIMITS["height_cm"]["min"], LIMITS["height_cm"]["max"]
    if not _NUMBER.fullmatch(raw):
        raise Invalid(f"Enter your height as a number in cm, between {lo} and {hi}.")
    height = float(raw)
    if not lo <= height <= hi:
        raise Invalid(f"Height must be between {lo} and {hi} cm. Leave it empty and we estimate it from the table.")
    return height


def text(raw: str, key: str, label: str) -> str:
    """Trimmed text no longer than LIMITS["text_chars"][key]."""
    value = raw.strip()
    most = LIMITS["text_chars"][key]
    if len(value) > most:
        raise Invalid(f"{label} can be up to {most} characters (it has {len(value)}). Shorten it and try again.")
    return value


def upload_name(filename: str | None, size: int | None) -> str:
    """Checks the extension and size before the file is saved. Returns the lower-case suffix."""
    up = LIMITS["upload"]
    suffix = Path(filename or "").suffix.lower()
    if suffix.lstrip(".") not in up["extensions"]:
        names = _or([e.upper() if e != "webm" else "WebM" for e in up["extensions"]])
        raise Invalid(f"Upload a video file: {names}.")
    if size is not None and size > up["max_mb"] * 1_000_000:
        raise Invalid(f"That file is {size / 1e6:.0f} MB. Upload one under {up['max_mb']} MB, or trim it first.")
    return suffix


def probe(path: Path) -> dict:
    """Video tracks (cover art excluded), size and duration, via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height:stream_disposition=attached_pic:format=duration",
             "-of", "json", str(path)],
            check=True, capture_output=True, text=True, timeout=60).stdout
        data = json.loads(out)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        raise Invalid("We couldn't read that file as a video. Export it again as MP4 or MOV and retry.") from e
    # An audio file with cover art shows up as a "video" stream flagged attached_pic.
    video = [s for s in data.get("streams", []) if s.get("codec_type") == "video"
             and not (s.get("disposition") or {}).get("attached_pic")]
    try:
        duration = float(data.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        duration = None
    first = video[0] if video else {}
    return {"has_video": bool(video), "width": first.get("width") or 0, "height": first.get("height") or 0,
            "duration": duration}


def video_file(path: Path) -> dict:
    """Rejects files the pipelines can't use: no video track, too short or long, under 240p."""
    up = LIMITS["upload"]
    info = probe(path)
    if not info["has_video"]:
        raise Invalid("That file has no video track, only sound. Upload the video itself.")
    if info["duration"] is None:
        raise Invalid("We couldn't tell how long that video is. Export it again as MP4 and retry.")
    if info["duration"] < up["min_seconds"]:
        raise Invalid(f"That clip is only {info['duration']:.1f} s long. Upload at least {up['min_seconds']} seconds of play.")
    if info["duration"] > up["max_seconds"]:
        raise Invalid(f"That video is {fmt_duration(info['duration'])} long. Uploads can be up to "
                      f"{up['max_seconds'] // 60} minutes: trim it and try again.")
    if min(info["width"], info["height"]) < up["min_short_side"]:
        raise Invalid(f"That video is only {info['width']}x{info['height']}, too small to see the stroke. "
                      "Re-record it at 480p or higher (your phone's normal video setting is fine).")
    return info


def player_frames(frames: list[tuple[str | None, bytes]], times: str) -> list[tuple[float, bytes]]:
    """Still frames the browser grabbed from the chosen video, for finding the players: 1 to
    max_frames JPEG/PNG images of at most max_frame_kb, with one time (s) each in `times`."""
    lim = LIMITS["players"]
    if not frames:
        raise Invalid("Send at least one frame of the video, or a YouTube link.")
    if len(frames) > lim["max_frames"]:
        raise Invalid(f"Send at most {lim['max_frames']} frames.")
    stamps = [t for t in times.split(",") if t.strip()]
    if len(stamps) != len(frames) or not all(_NUMBER.fullmatch(t.strip()) for t in stamps):
        raise Invalid("Each frame needs its time in the video, in seconds.")
    out = []
    for (name, data), stamp in zip(frames, stamps):
        if len(data) > lim["max_frame_kb"] * 1024:
            raise Invalid(f"Each frame must be under {lim['max_frame_kb']} KB.")
        if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
            raise Invalid("Frames must be JPEG or PNG images.")
        out.append((float(stamp), data))
    return out

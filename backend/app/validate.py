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
from messages import Keyed, Msg, one_of


class Invalid(Keyed):
    """Bad input. The message is shown to the user: in English as written, or translated by the
    page from its reference when it was built from a Msg (messages.py)."""


# The field labels the endpoints pass, as message keys so the page can translate them.
_LABELS = {"Bat hand": "hand", "Stroke": "stroke", "Grip": "grip", "Mode": "mode", "Language": "language",
           "Your request": "request", "The player's name": "playerName",
           "The training description": "trainingDescription", "Rallies in the reel": "topN",
           "Hit threshold": "threshold", "Max gap": "gap", "Min hits": "minHits", "Height": "height"}


def label_(text: str) -> "Msg | str":
    return Msg(f"validation.labels.{_LABELS[text]}") if text in _LABELS else text


_NUMBER = re.compile(r"[0-9]+(\.[0-9]+)?")  # ASCII only, like the form's check


def _num(v: float) -> str:
    return f"{v:g}"


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def choice(value: str, key: str, label: str) -> str:
    """value must be one of LIMITS["choices"][key] (the options the form offers)."""
    if value not in LIMITS["choices"][key]:
        raise Invalid(Msg("validation.choice", label=label_(label), options=one_of(LIMITS["choices"][key])))
    return value


def in_range(value: float, key: str, label: str) -> float:
    """An Auto-Cut setting within LIMITS["autocut"][key]. NaN fails the comparison too."""
    lo, hi = LIMITS["autocut"][key]["min"], LIMITS["autocut"][key]["max"]
    if not lo <= value <= hi:
        raise Invalid(Msg("validation.between", label=label_(label), min=_num(lo), max=_num(hi)))
    return value


def height_cm(raw: str) -> float | None:
    """Optional height in cm. Plain digits only, so text, negatives, hex and exponents fail."""
    raw = raw.strip()
    if not raw:
        return None
    lo, hi = LIMITS["height_cm"]["min"], LIMITS["height_cm"]["max"]
    if not _NUMBER.fullmatch(raw):
        raise Invalid(Msg("validation.heightNumber", min=lo, max=hi))
    height = float(raw)
    if not lo <= height <= hi:
        raise Invalid(Msg("validation.heightRange", min=lo, max=hi))
    return height


def text(raw: str, key: str, label: str) -> str:
    """Trimmed text no longer than LIMITS["text_chars"][key]."""
    value = raw.strip()
    most = LIMITS["text_chars"][key]
    if len(value) > most:
        raise Invalid(Msg("validation.textLength", label=label_(label), max=most, n=len(value)))
    return value


def upload_name(filename: str | None, size: int | None) -> str:
    """Checks the extension and size before the file is saved. Returns the lower-case suffix."""
    up = LIMITS["upload"]
    suffix = Path(filename or "").suffix.lower()
    if suffix.lstrip(".") not in up["extensions"]:
        names = one_of([e.upper() if e != "webm" else "WebM" for e in up["extensions"]])
        raise Invalid(Msg("validation.uploadType", types=names))
    if size is not None and size > up["max_mb"] * 1_000_000:
        raise Invalid(Msg("validation.uploadSize", mb=f"{size / 1e6:.0f}", max=up["max_mb"]))
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
        raise Invalid(Msg("serverErrors.unreadable")) from e
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
        raise Invalid(Msg("serverErrors.noVideoTrack"))
    if info["duration"] is None:
        raise Invalid(Msg("serverErrors.noDuration"))
    if info["duration"] < up["min_seconds"]:
        raise Invalid(Msg("validation.tooShort", seconds=f"{info['duration']:.1f}", min=up["min_seconds"]))
    if info["duration"] > up["max_seconds"]:
        raise Invalid(Msg("validation.tooLong", length=fmt_duration(info["duration"]),
                          max=Msg("common.minutes", n=up["max_seconds"] // 60)))
    if min(info["width"], info["height"]) < up["min_short_side"]:
        raise Invalid(Msg("validation.tooSmall", width=info["width"], height=info["height"]))
    return info


def player_frames(frames: list[tuple[str | None, bytes]], times: str) -> list[tuple[float, bytes]]:
    """Still frames the browser grabbed from the chosen video, for finding the players: 1 to
    max_frames JPEG/PNG images of at most max_frame_kb, with one time (s) each in `times`."""
    lim = LIMITS["players"]
    if not frames:
        raise Invalid(Msg("validation.sendFrames"))
    if len(frames) > lim["max_frames"]:
        raise Invalid(Msg("validation.maxFrames", max=lim["max_frames"]))
    stamps = [t for t in times.split(",") if t.strip()]
    if len(stamps) != len(frames) or not all(_NUMBER.fullmatch(t.strip()) for t in stamps):
        raise Invalid(Msg("validation.frameTimes"))
    out = []
    for (name, data), stamp in zip(frames, stamps):
        if len(data) > lim["max_frame_kb"] * 1024:
            raise Invalid(Msg("validation.frameSize", max=lim["max_frame_kb"]))
        if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
            raise Invalid(Msg("validation.frameType"))
        out.append((float(stamp), data))
    return out


def only_me(value: str) -> bool:
    """The "Only me in the video" box: "1" when ticked, "" when not."""
    if value not in LIMITS["choices"]["only_me"]:
        raise Invalid(Msg("validation.onlyMe"))
    return value == "1"


PICK_AGAIN = Msg("validation.pickAgain")


def player_selection(time_raw: str, box_raw: str) -> tuple[float, tuple[float, float, float, float]] | None:
    """The player tapped in "Which one is you?": a frame time (s) and a normalised box
    "x0,y0,x1,y1". Both blank means no choice (the analysis picks the player itself)."""
    time_raw, box_raw = time_raw.strip(), box_raw.strip()
    if not time_raw and not box_raw:
        return None
    parts = [v.strip() for v in box_raw.split(",")]
    if not _NUMBER.fullmatch(time_raw) or len(parts) != 4 or not all(_NUMBER.fullmatch(v) for v in parts):
        raise Invalid(PICK_AGAIN)
    x0, y0, x1, y1 = map(float, parts)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise Invalid(PICK_AGAIN)
    return float(time_raw), (x0, y0, x1, y1)

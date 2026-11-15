"""Fetch a pasted YouTube link with yt-dlp so the normal upload pipeline can run on it.

Only YouTube watch, youtu.be and Shorts links are accepted. Videos are capped at 720p and
3 minutes; `probe()` runs before the job is created so a bad link fails on the form."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

MAX_SECONDS = 180
MAX_HEIGHT = 720

_ID = r"([\w-]{11})"
_PATTERNS = [
    re.compile(rf"^(?:https?://)?(?:www\.|m\.)?youtube\.com/watch\?(?:.*&)?v={_ID}(?:[&#].*)?$"),
    re.compile(rf"^(?:https?://)?(?:www\.|m\.)?youtube\.com/shorts/{_ID}(?:[/?#].*)?$"),
    re.compile(rf"^(?:https?://)?youtu\.be/{_ID}(?:[/?#].*)?$"),
]

# yt-dlp needs a JavaScript runtime for YouTube; Node is already required by the frontend.
# Bounded network waits: the probe runs while the user's form is waiting for an answer.
_BASE_OPTS = {"quiet": True, "no_warnings": True, "noplaylist": True, "js_runtimes": {"node": {}},
              "socket_timeout": 15, "retries": 2, "extractor_retries": 1}


class LinkError(ValueError):
    """A problem with the link that the user can fix. The message is shown as-is."""


class _QuietLogger:
    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


def video_id(url: str) -> str:
    """The 11-character video id, or LinkError if this isn't a supported YouTube link."""
    url = (url or "").strip()
    for p in _PATTERNS:
        m = p.match(url)
        if m:
            return m.group(1)
    raise LinkError("That isn't a YouTube link we can use. Paste a youtube.com/watch, youtu.be or Shorts link.")


def canonical(url: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id(url)}"


def _friendly(err: Exception) -> LinkError:
    msg = str(err)
    low = msg.lower()
    if "private video" in low:
        return LinkError("That video is private. Use a public or unlisted video.")
    if "confirm your age" in low or "age-restricted" in low:
        return LinkError("That video is age-restricted, so we can't download it. Try another link.")
    if "members-only" in low or "join this channel" in low:
        return LinkError("That video is for channel members only. Try a public video.")
    if "not a bot" in low:
        return LinkError("YouTube is blocking downloads from this server right now. Upload the file instead.")
    if "unavailable" in low or "removed" in low or "does not exist" in low:
        return LinkError("That video is unavailable. Check the link, or it may have been removed.")
    return LinkError(f"Couldn't open that video: {msg.removeprefix('ERROR: ').strip()[:160]}")


def probe(url: str) -> dict:
    """Read the video's metadata without downloading. Raises LinkError for anything the
    user should hear about before a job starts (private, too long, live...)."""
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({**_BASE_OPTS, "skip_download": True, "logger": _QuietLogger()}) as ydl:
            info = ydl.extract_info(canonical(url), download=False)
    except yt_dlp.utils.DownloadError as e:
        raise _friendly(e) from e
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise LinkError("Live streams aren't supported. Use a regular video.")
    duration = info.get("duration") or 0
    if duration > MAX_SECONDS:
        m, s = divmod(int(duration), 60)
        raise LinkError(f"That video is {m}:{s:02d} long. Use one under 3 minutes, or trim it and upload the file.")
    return {"id": info.get("id"), "title": info.get("title"), "duration": duration,
            "uploader": info.get("uploader"), "url": canonical(url)}


def download(url: str, dest_dir: Path, stem: str = "input",
             progress: Callable[[float], None] | None = None) -> Path:
    """Download at <=720p (shorter side) into dest_dir/<stem>.mp4 (merged video + audio). Returns the path."""
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)

    def hook(d: dict) -> None:
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progress(min(1.0, d.get("downloaded_bytes", 0) / total))

    opts = {
        **_BASE_OPTS,
        "logger": _QuietLogger(),
        # "res" is the smaller side, so this caps Shorts (portrait) at 720x1280 too.
        # H.264 + AAC plays everywhere and decodes fast in OpenCV.
        "format": "bv*+ba/b",
        "format_sort": [f"res:{MAX_HEIGHT}", "vcodec:h264", "acodec:m4a"],
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / f"{stem}.%(ext)s"),
        "progress_hooks": [hook],
        # Second guard in case the metadata changed between probe and download.
        "match_filter": lambda info, *_: (
            "too long" if (info.get("duration") or 0) > MAX_SECONDS else None),
    }
    for attempt in (1, 2):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(canonical(url), download=True)
            break
        except yt_dlp.utils.DownloadError as e:
            err = _friendly(e)
            # YouTube sometimes fails one request (403, expired format URL); retry once.
            if attempt == 2 or not str(err).startswith("Couldn't open"):
                raise err from e
    files = [Path(r["filepath"]) for r in info.get("requested_downloads", []) if r.get("filepath")]
    path = next((f for f in files if f.exists()), None)
    if path is None:
        matches = sorted(dest_dir.glob(f"{stem}.*"))
        if not matches:
            raise LinkError("The download finished but no video file was saved. Try again.")
        path = matches[0]
    return path

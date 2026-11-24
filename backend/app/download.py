"""Fetch a pasted YouTube link with yt-dlp so the normal upload pipeline can run on it.

Only YouTube watch, youtu.be, Shorts and /live/ links are accepted. Videos are capped at
720p; the length cap depends on the page (shared/limits.json: 3 minutes for a stroke, 60 for
a match). `probe()` runs before the job is created so a bad link fails on the form."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from limits import LIMITS
from messages import Keyed, Msg

MAX_HEIGHT = 720
# The download's own guard; probe() has already applied the page's (lower) limit.
MAX_SECONDS = max(LIMITS["link_max_seconds"].values())

_ID = r"([\w-]{11})"
_PATTERNS = [
    re.compile(rf"^(?:https?://)?(?:www\.|m\.)?youtube\.com/watch\?(?:.*&)?v={_ID}(?:[&#].*)?$"),
    re.compile(rf"^(?:https?://)?(?:www\.|m\.)?youtube\.com/(?:shorts|live)/{_ID}(?:[/?#].*)?$"),
    re.compile(rf"^(?:https?://)?youtu\.be/{_ID}(?:[/?#].*)?$"),
]
_YOUTUBE = re.compile(r"^(?:https?://)?(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)(?:[/?#]|$)", re.I)
_PLAYLIST = re.compile(r"^(?:https?://)?(?:www\.|m\.)?youtube\.com/playlist\b", re.I)
_CHANNEL = re.compile(r"^(?:https?://)?(?:www\.|m\.)?youtube\.com/(?:@|channel/|c/|user/)", re.I)
LINK_HINT = "Paste a youtube.com/watch, youtu.be or Shorts link."

# yt-dlp needs a JavaScript runtime for YouTube; Node is already required by the frontend.
# Bounded network waits: the probe runs while the user's form is waiting for an answer.
_BASE_OPTS = {"quiet": True, "no_warnings": True, "noplaylist": True, "js_runtimes": {"node": {}},
              "socket_timeout": 15, "retries": 2, "extractor_retries": 1}


class LinkError(Keyed):
    """A problem with the link that the user can fix. The message is shown to the user (and
    translated by the page from its reference, messages.py)."""


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
    if _PLAYLIST.match(url):
        raise LinkError(Msg("validation.playlist"))
    if _CHANNEL.match(url):
        raise LinkError(Msg("validation.channel"))
    if not _YOUTUBE.match(url):
        raise LinkError(Msg("validation.notYoutube", hint=Msg("validation.linkHint")))
    raise LinkError(Msg("validation.badYoutube", hint=Msg("validation.linkHint")))


def canonical(url: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id(url)}"


def _friendly(err: Exception) -> LinkError:
    msg = str(err)
    low = msg.lower()
    if "private video" in low:
        return LinkError(Msg("serverErrors.link.private"))
    if "confirm your age" in low or "age-restricted" in low:
        return LinkError(Msg("serverErrors.link.ageRestricted"))
    if "members-only" in low or "join this channel" in low:
        return LinkError(Msg("serverErrors.link.membersOnly"))
    if "not a bot" in low:
        return LinkError(Msg("serverErrors.link.blocked"))
    if "live event will begin" in low or "premieres in" in low:
        return LinkError(Msg("serverErrors.link.notStarted"))
    if "unavailable" in low or "removed" in low or "does not exist" in low:
        return LinkError(Msg("serverErrors.link.unavailable"))
    return LinkError(Msg("serverErrors.link.couldntOpen", detail=msg.removeprefix("ERROR: ").strip()[:160]))


def max_seconds(kind: str) -> int:
    """How long a linked video may be on this page (breakdown, match, coach, autocut)."""
    return LIMITS["link_max_seconds"][kind]


def check_info(info: dict, kind: str) -> None:
    """LinkError for a video we won't fetch for this page: live, age-restricted, too long."""
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise LinkError(Msg("serverErrors.link.live"))
    if (info.get("age_limit") or 0) >= 18:
        raise LinkError(Msg("serverErrors.link.ageRestricted"))
    duration, most = info.get("duration") or 0, max_seconds(kind)
    if duration > most:
        m, s = divmod(int(duration), 60)
        raise LinkError(Msg("serverErrors.link.tooLong", length=f"{m}:{s:02d}", max=Msg("common.minutes", n=most // 60)))


def probe(url: str, kind: str = "breakdown") -> dict:
    """Read the video's metadata without downloading. Raises LinkError for anything the
    user should hear about before a job starts (private, too long for this page, live...)."""
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({**_BASE_OPTS, "skip_download": True, "logger": _QuietLogger()}) as ydl:
            info = ydl.extract_info(canonical(url), download=False)
    except yt_dlp.utils.DownloadError as e:
        raise _friendly(e) from e
    check_info(info, kind)
    return {"id": info.get("id"), "title": info.get("title"), "duration": info.get("duration") or 0,
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
            raise LinkError(Msg("serverErrors.link.noFile"))
        path = matches[0]
    return path

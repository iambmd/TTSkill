"""Input checks without the API: the shared limits file, height, choices, ranges, text,
upload names, the ffprobe checks, YouTube link shapes and metadata, the Auto-Cut
warning and the "is there a player" check after pose."""
import json

import numpy as np
import pytest

from app import download, pipelines, validate
from conftest import make_media
from limits import FILE, LIMITS
from technique.pose import NoPlayer, PoseTrack, require_player


def test_limits_file_is_the_one_the_frontend_reads():
    assert FILE.name == "limits.json" and FILE.parent.name == "shared"
    assert json.loads(FILE.read_text()) == LIMITS
    assert LIMITS["height_cm"] == {"min": 100, "max": 230}
    assert LIMITS["upload"]["extensions"] == ["mp4", "mov", "webm", "mkv"]


@pytest.mark.parametrize("raw,expect", [
    ("", None), ("  ", None), ("175", 175.0), (" 182.5 ", 182.5), ("100", 100.0), ("230", 230.0),
])
def test_height_ok(raw, expect):
    assert validate.height_cm(raw) == expect


@pytest.mark.parametrize("raw", ["250", "0", "99.9", "230.01", "-170", "abc", "5'10", "nan", "inf",
                                 "1e2", "0x64", "175cm", "１７５"])
def test_height_rejected(raw):
    with pytest.raises(validate.Invalid, match="cm"):
        validate.height_cm(raw)


def test_choices_and_ranges():
    assert validate.choice("penhold", "grip", "Grip") == "penhold"
    with pytest.raises(validate.Invalid, match="Grip must be shakehand or penhold."):
        validate.choice("Penhold", "grip", "Grip")
    with pytest.raises(validate.Invalid, match="Bat hand must be auto, left or right."):
        validate.choice("", "hand", "Bat hand")
    assert validate.in_range(3.0, "threshold", "Hit threshold") == 3.0
    for bad in (1.4, 10.1, float("nan"), float("inf")):
        with pytest.raises(validate.Invalid, match="between 1.5 and 10"):
            validate.in_range(bad, "threshold", "Hit threshold")


def test_text_is_trimmed_then_counted():
    assert validate.text("  " + "a" * 1000 + "\n", "coach_request", "Your request") == "a" * 1000
    with pytest.raises(validate.Invalid, match=r"up to 1000 characters \(it has 1001\)"):
        validate.text("a" * 1001, "coach_request", "Your request")


@pytest.mark.parametrize("name", ["clip.mp4", "IMG_8782.MOV", "rec.webm", "a.b.MKV"])
def test_upload_names_ok(name):
    assert validate.upload_name(name, 1000) == "." + name.rsplit(".", 1)[1].lower()


@pytest.mark.parametrize("name", ["clip.avi", "clip.m4v", "clip.3gp", "clip", "", None, "mp4"])
def test_upload_names_rejected(name):
    with pytest.raises(validate.Invalid, match="MP4, MOV, WebM or MKV"):
        validate.upload_name(name, 1000)


def test_upload_size_limit():
    assert validate.upload_name("a.mp4", 500_000_000)
    with pytest.raises(validate.Invalid, match="That file is 501 MB. Upload one under 500 MB"):
        validate.upload_name("a.mp4", 501_000_000)


def test_video_file_checks(media, tmp_path):
    info = validate.video_file(media["ok"])
    assert info["has_video"] and (info["width"], info["height"]) == (640, 360) and 2.9 < info["duration"] < 3.2
    assert validate.video_file(make_media(tmp_path / "upright.mp4", size="240x426"))  # 240p portrait is fine
    for name, expect in [("short", "at least 2 seconds"), ("tiny", "Re-record it"), ("sound_only", "no video track")]:
        with pytest.raises(validate.Invalid, match=expect):
            validate.video_file(media[name])


def test_audio_with_cover_art_counts_as_no_video(media, tmp_path):
    """An m4a/mp3 with album art probes as a 'video' stream flagged attached_pic."""
    import subprocess
    art = tmp_path / "art.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=red:size=320x320", "-frames:v", "1",
                    str(art)], check=True)
    song = tmp_path / "song.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(media["sound_only"]), "-i", str(art), "-map", "0:a",
                    "-map", "1:v", "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v", "attached_pic", str(song)],
                   check=True)
    assert not validate.probe(song)["has_video"]
    with pytest.raises(validate.Invalid, match="no video track"):
        validate.video_file(song)


def test_unreadable_file(tmp_path):
    bad = tmp_path / "x.mp4"
    bad.write_bytes(b"\x00" * 100)
    with pytest.raises(validate.Invalid, match="couldn't read that file as a video"):
        validate.video_file(bad)


# ------------------------------------------------------------------ YouTube links

@pytest.mark.parametrize("url,expect", [
    ("https://www.youtube.com/playlist?list=PLx1", "That's a playlist"),
    ("youtube.com/playlist?list=PLx1", "That's a playlist"),
    ("https://www.youtube.com/@pingskills", "That's a channel link"),
    ("https://www.youtube.com/channel/UC1234567890", "That's a channel link"),
    ("https://youtube.com/c/PingSkills", "That's a channel link"),
    ("https://m.youtube.com/user/pingskills", "That's a channel link"),
    ("https://vimeo.com/123", "Only YouTube links work here"),
    ("https://evil.com/youtu.be/g3n9jVP0fMU", "Only YouTube links work here"),
    ("https://www.youtube.com/feed/trending", "isn't a YouTube video link"),
    ("https://www.youtube.com/watch?v=short", "isn't a YouTube video link"),
])
def test_link_shape_errors(url, expect):
    with pytest.raises(download.LinkError, match=expect):
        download.video_id(url)


def test_live_links_and_videos_in_a_playlist_are_accepted():
    assert download.video_id("https://www.youtube.com/live/g3n9jVP0fMU?si=x") == "g3n9jVP0fMU"
    assert download.video_id("https://www.youtube.com/watch?v=g3n9jVP0fMU&list=PLx1&index=2") == "g3n9jVP0fMU"


@pytest.mark.parametrize("info,expect", [
    ({"is_live": True, "duration": None}, "live stream"),
    ({"live_status": "is_upcoming"}, "live stream"),
    ({"age_limit": 18, "duration": 30}, "age-restricted"),
    ({"duration": 181}, "3:01 long. Use one under 3 minutes"),
])
def test_metadata_errors(info, expect):
    with pytest.raises(download.LinkError, match=expect):
        download.check_info(info, "breakdown")


def test_link_length_depends_on_the_page():
    download.check_info({"duration": 180}, "breakdown")
    download.check_info({"duration": 45 * 60}, "autocut")  # a whole match is fine on Auto-Cut
    with pytest.raises(download.LinkError, match="Use one under 3 minutes"):
        download.check_info({"duration": 45 * 60}, "match")
    with pytest.raises(download.LinkError, match="61:00 long. Use one under 60 minutes"):
        download.check_info({"duration": 61 * 60}, "autocut")
    assert download.MAX_SECONDS == 3600


@pytest.mark.parametrize("raw,expect", [
    ("ERROR: [youtube] x: This live event will begin in 3 hours.", "hasn't started"),
    ("ERROR: Sign in to confirm your age. This video may be inappropriate", "age-restricted"),
])
def test_friendly_live_and_age_errors(raw, expect):
    assert expect in str(download._friendly(Exception(raw)))


# ------------------------------------------------------------------ Auto-Cut warning and pose check

def test_few_rallies_warning():
    assert "didn't hear any rallies" in pipelines.few_rallies_warning(0)
    one = pipelines.few_rallies_warning(1)
    assert "only heard 1 rally." in one and "closer to the table" in one and "background noise" in one
    assert pipelines.few_rallies_warning(2) is None


def _track(valid: int, n: int = 100) -> PoseTrack:
    lm = np.full((n, 33, 4), np.nan, np.float32)
    lm[:valid] = 0.5
    return PoseTrack(fps=30, width=640, height=360, times=np.arange(n) / 30, lm=lm,
                     world=np.zeros((n, 33, 3), np.float32))


def test_require_player():
    assert require_player(_track(40)) == pytest.approx(0.4)
    assert require_player(_track(100)) == 1.0
    with pytest.raises(NoPlayer, match="only see the player in 39% of the clip. Film a clearer clip"):
        require_player(_track(39))
    with pytest.raises(NoPlayer, match="in 39% of"):  # 39.6% is under 40%, so it mustn't say 40%
        require_player(_track(396, n=1000))
    with pytest.raises(NoPlayer, match="couldn't find a player"):
        require_player(_track(0))
    with pytest.raises(NoPlayer, match="couldn't find a player"):
        require_player(_track(0, n=0))

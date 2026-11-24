"""Every message the backend shows a user, in English, keyed by its path in
frontend/messages/{en,vi}.json, where the translations live.

The backend writes the English text as before, and next to it a reference the page translates
into the reader's language: job progress (`messageRef`), failures (`failureRef`), warnings
(`warningRef`) and 422 answers (`detailRef`). A reference is {"key": ..., "args": {...}}; an
argument can itself be a reference (a field label, "10 minutes").
tests/test_messages.py checks every key here is in both frontend catalogues with the same text."""
from __future__ import annotations

from typing import Any, Callable

_CLEARER = "Film a clearer clip: the whole body in frame, side-on if you can, in good light."
_LOST_PICK = ("Pick them in a frame where they're clearly in view, film closer, or trim the video "
              "to the part where they play.")
_QUIETER = "Try filming closer to the table or somewhere with less background noise."

EN: dict[str, str | Callable[..., str]] = {
    # Shared pieces (already in the frontend's catalogue).
    "common.minutes": lambda n: f"{n} minute" + ("" if n == 1 else "s"),
    "validation.or": "{list} or {last}",
    "validation.linkHint": "Paste a youtube.com/watch, youtu.be or Shorts link.",
    "validation.labels.hand": "Bat hand",
    "validation.labels.stroke": "Stroke",
    "validation.labels.grip": "Grip",
    "validation.labels.mode": "Mode",
    "validation.labels.language": "Language",
    "validation.labels.request": "Your request",
    "validation.labels.playerName": "The player's name",
    "validation.labels.trainingDescription": "The training description",
    "validation.labels.topN": "Rallies in the reel",
    "validation.labels.threshold": "Hit threshold",
    "validation.labels.gap": "Max gap",
    "validation.labels.minHits": "Min hits",
    "validation.labels.height": "Height",
    # Checks the form runs too: the same keys and words as frontend/lib/validate.ts.
    "validation.choice": "{label} must be {options}.",
    "validation.between": "{label} must be between {min} and {max}.",
    "validation.wholeNumber": "{label} must be a whole number.",
    "validation.number": "{label} must be a number.",
    "validation.heightNumber": "Enter your height as a number in cm, between {min} and {max}.",
    "validation.heightRange": "Height must be between {min} and {max} cm. Leave it empty and we estimate it from the table.",
    "validation.textLength": "{label} can be up to {max} characters (it has {n}). Shorten it and try again.",
    "validation.uploadType": "Upload a video file: {types}.",
    "validation.uploadSize": "That file is {mb} MB. Upload one under {max} MB, or trim it first.",
    "validation.tooShort": "That clip is only {seconds} s long. Upload at least {min} seconds of play.",
    "validation.tooLong": "That video is {length} long. Uploads can be up to {max}: trim it and try again.",
    "validation.tooSmall": ("That video is only {width}x{height}, too small to see the stroke. Re-record it at 480p "
                            "or higher (your phone's normal video setting is fine)."),
    "validation.sendFrames": "Send at least one frame of the video, or a YouTube link.",
    "validation.maxFrames": "Send at most {max} frames.",
    "validation.frameTimes": "Each frame needs its time in the video, in seconds.",
    "validation.frameSize": "Each frame must be under {max} KB.",
    "validation.frameType": "Frames must be JPEG or PNG images.",
    "validation.onlyMe": "“Only me in the video” must be ticked or not.",
    "validation.pickAgain": "The player you picked didn't come through. Pick the player again.",
    "validation.playlist": "That's a playlist. Open one video from it and paste that video's link.",
    "validation.channel": "That's a channel link. Open one of its videos and paste that video's link.",
    "validation.notYoutube": "Only YouTube links work here. {hint} Or upload the file.",
    "validation.badYoutube": "That isn't a YouTube video link we can use. {hint}",
    "validation.unknownStroke": "Unknown stroke: {stroke}. Leave it blank to auto-detect.",
    "validation.unknownStrokeType": "Unknown stroke type: {stroke}. Pick one from the list, or leave it blank to auto-detect.",
    "validation.breakdownInput": "Upload a clip, paste a YouTube link, or describe the training.",
    "validation.coachRequest": "Tell the coach what you want, e.g. 'show my best rallies and fix my forehand'.",
    "validation.coachVideo": "Add a video: upload a clip or paste a YouTube link.",
    "validation.matchVideo": "Upload a clip of yourself or paste a YouTube link.",
    "validation.autocutVideo": "Upload a match video or paste a YouTube link.",
    "validation.chooseVideoAgain": "Choose the video again.",
    "validation.unknownJob": "Unknown job.",
    "errors.pickRally": "Choose at least one available rally, once each.",
    # Checks only the server can run.
    "serverErrors.unreadable": "We couldn't read that file as a video. Export it again as MP4 or MOV and retry.",
    "serverErrors.noVideoTrack": "That file has no video track, only sound. Upload the video itself.",
    "serverErrors.noDuration": "We couldn't tell how long that video is. Export it again as MP4 and retry.",
    "serverErrors.uploadExpired": "Your upload expired. Choose the video again.",
    "serverErrors.finishedMatch": "Open a finished match result to use that video.",
    "serverErrors.rallyGone": "That rally is no longer available. Open the match result and choose again.",
    "serverErrors.videoGone": "This video is no longer available. Choose the video again.",
    "serverErrors.frameUnreadable": "A frame couldn't be read as an image.",
    "serverErrors.kind": "kind must be breakdown, match or coach.",
    "serverErrors.jobVideoGone": "This job's video is no longer here. Upload it again to pick a player.",
    "serverErrors.changePlayerKinds": "Only Breakdown, Pro match and Coach results can change player.",
    "serverErrors.clipsGone": "Some rally clips are no longer available. Upload the match again.",
    "serverErrors.missing": "{label} is missing.",
    "serverErrors.notValid": "{label} isn't valid.",
    "serverErrors.link.private": "That video is private. Use a public or unlisted video.",
    "serverErrors.link.ageRestricted": "That video is age-restricted, so we can't download it. Try another link.",
    "serverErrors.link.membersOnly": "That video is for channel members only. Try a public video.",
    "serverErrors.link.blocked": "YouTube is blocking downloads from this server right now. Upload the file instead.",
    "serverErrors.link.notStarted": ("That's a live stream that hasn't started. Live videos aren't supported: "
                                     "use a regular video."),
    "serverErrors.link.unavailable": "That video is unavailable. Check the link, or it may have been removed.",
    "serverErrors.link.couldntOpen": "Couldn't open that video: {detail}",
    "serverErrors.link.live": ("That's a live stream. Live videos aren't supported: wait until it ends, "
                               "or use a regular video."),
    "serverErrors.link.tooLong": "That video is {length} long. Use one under {max}, or trim it and upload the file.",
    "serverErrors.link.noFile": "The download finished but no video file was saved. Try again.",
    "serverErrors.player.lostPick": "We lost the player you picked: we could see them {seen}. " + _LOST_PICK,
    "serverErrors.player.seenPct": "only in {pct}% of the clip",
    "serverErrors.player.seenNowhere": "anywhere in the analysed part of the clip",
    "serverErrors.player.none": "We couldn't find a player in this clip. " + _CLEARER,
    "serverErrors.player.onlySeen": "We could only see the player in {pct}% of the clip. " + _CLEARER,
    "serverErrors.player.cantReadAt": "We couldn't read the video at {when}, where you picked the player. Pick again.",
    "serverErrors.player.notFoundAt": "We couldn't find the player you picked at {when}. Pick again, or trim the video.",
    "serverErrors.player.hand": "We couldn't tell your hitting hand. Choose left or right, or upload a clearer swing.",
    # Job progress, results and failures.
    "progress.waiting": "Waiting for the worker. Start it with `make dev` (or `make worker`).",
    "progress.restarted": "The server restarted before this job finished. Please try again.",
    "progress.workerRestarted": "The worker restarted before this job finished. Please try again.",
    "progress.unfinished": "The job stopped without finishing. Please try again.",
    "progress.failed": "We couldn't finish this analysis. Try again or upload a shorter clip.",
    "progress.timeout": "This took longer than {minutes} minutes, so we stopped it. Try a shorter clip, or try again.",
    "progress.starting": "Starting...",
    "progress.downloading": "Downloading the video...",
    "progress.downloadingPct": "Downloading the video... {pct}%",
    "progress.autocut.none": "No rallies found.",
    "progress.autocut.doneTop": "Top {n} rallies, {seconds} seconds.",
    "progress.autocut.doneAll": "All {n} rallies, {seconds} seconds.",
    "progress.autocut.failed": "We couldn't make a reel. Try a shorter MP4 or MOV recording with sound.",
    "progress.autocut.heardNone": "We didn't hear any rallies. " + _QUIETER,
    "progress.autocut.heardOne": "We only heard 1 rally. " + _QUIETER,
    "progress.autocut.heardFew": "We only heard {n} rallies. " + _QUIETER,
    "progress.breakdown.start": "Starting the breakdown...",
    "progress.breakdown.onlyMe": "Finding who plays the most...",
    "progress.breakdown.reading": "Reading your video...",
    "progress.breakdown.finding": "Finding the stroke...",
    "progress.breakdown.pose": "Tracking the player's body...",
    "progress.breakdown.hand": "Finding the bat hand...",
    "progress.breakdown.strokeType": "Working out the stroke...",
    "progress.breakdown.analysing": "Writing the coaching cards...",
    "progress.breakdown.rendering": "Rendering the coaching video...",
    "progress.breakdown.finishing": "Finishing up...",
    "progress.breakdown.done": "{headline} ({analyzer} analyzer)",
    "progress.breakdown.ready": "Breakdown ready",
    "progress.match.swings": "Finding your best swings...",
    "progress.match.reading": "Reading your body and swing with MediaPipe...",
    "progress.match.height": "Estimating your height from the table...",
    "progress.match.pros": "Comparing you with the pros...",
    "progress.match.compile": "Putting their breakdowns together...",
    "progress.match.done": "You play most like {name} ({score}% body match).",
}


class Msg:
    """One message: its key, and arguments (plain values or other Msg)."""

    def __init__(self, key: str, **args: Any):
        if key not in EN:
            raise KeyError(f"no message {key!r} in backend/messages.py")
        self.key, self.args = key, args

    def __str__(self) -> str:
        values = {k: str(v) if isinstance(v, Msg) else v for k, v in self.args.items()}
        text = EN[self.key]
        return text(**values) if callable(text) else text.format(**values)

    def ref(self) -> dict:
        return {"key": self.key, "args": {k: v.ref() if isinstance(v, Msg) else v for k, v in self.args.items()}}

    def fields(self, text: str = "message") -> dict:
        """Job fields for this message: the English text and, beside it, its reference
        ("message" -> messageRef, "warning" -> warningRef)."""
        return {text: str(self), f"{text}Ref": self.ref()}


def say(key: str, **args: Any) -> dict:
    """Job fields for a progress message: the English text and its reference."""
    return Msg(key, **args).fields()


def one_of(options: list[str]) -> Msg | str:
    """"a, b or c" with the reader's word for "or"."""
    return Msg("validation.or", list=", ".join(options[:-1]), last=options[-1]) if len(options) > 1 else options[0]


class Keyed(ValueError):
    """An error whose text the user reads: built from a Msg, it carries the reference too."""

    def __init__(self, message: "Msg | str"):
        super().__init__(str(message))
        self.ref = message.ref() if isinstance(message, Msg) else None

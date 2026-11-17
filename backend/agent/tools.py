"""The coach agent's tools: thin wrappers over the existing pipelines, bound to one job.

Each function does real work (10-60 s), records any video it makes as a job output, and
returns a small JSON-able dict. `make_tools()` exposes them to LangChain; the fallback in
coach.py calls the same functions directly."""
from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field

from app import download as dl
from app import jobs
from app.cut import cut_and_concat
from app.pipelines import match_video, pick_segments
from app.rally import detect_rallies as find_rallies

_LOCK = threading.Lock()  # tools may run in parallel; job.json is read-modify-write


class ToolError(RuntimeError):
    """A problem the agent can act on; the message goes back to it."""


@dataclass
class Session:
    job_id: str
    video: Optional[Path] = None
    url: Optional[str] = None
    rallies: list = field(default_factory=list)
    pose: Optional[dict] = None

    @property
    def dir(self) -> Path:
        return jobs.job_dir(self.job_id)

    def update(self, **fields) -> None:
        with _LOCK:
            jobs.update(self.job_id, **fields)

    def add_output(self, kind: str, title: str, filename: str, summary: str) -> None:
        with _LOCK:
            job = jobs.load(self.job_id) or {}
            outs = [o for o in job.get("outputs", []) if o["kind"] != kind]
            outs.append({"kind": kind, "title": title, "url": f"/jobs/{self.job_id}/files/{filename}",
                         "summary": summary})
            jobs.update(self.job_id, outputs=outs)

    def need_video(self) -> Path:
        if self.video is None or not self.video.exists():
            if self.url:
                raise ToolError(f"No video loaded yet. Call download_url with {self.url} first.")
            raise ToolError("No video was provided. Ask the user to upload one or paste a link.")
        return self.video


# ------------------------------------------------------------------ the six tools

def download_url(s: Session, url: str) -> dict:
    info = dl.probe(url, "coach")
    s.update(message=f"Downloading {info['title']}...")
    s.video = dl.download(url, s.dir)
    return {"title": info["title"], "duration_s": info["duration"], "loaded": True}


def detect_rallies(s: Session, threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4) -> dict:
    video = s.need_video()
    s.update(message="Listening for ball contacts...")
    s.rallies = find_rallies(video, s.dir, threshold, gap, min_hits)
    from app.floor_bounce import drop_non_play
    s.rallies, _ = drop_non_play(video, s.rallies)
    rs = [r.to_dict() for r in s.rallies]
    return {"count": len(rs), "rallies": rs[:25],
            "longest": max(rs, key=lambda r: r["shots"]) if rs else None,
            "hint": None if rs else "No rallies heard. Try threshold 2.5 or min_hits 3."}


def cut_highlights(s: Session, mode: str = "highlights", top_n: int = 5) -> dict:
    video = s.need_video()
    if mode not in ("highlights", "full"):
        raise ToolError("mode must be 'highlights' or 'full'")
    if not s.rallies:
        detect_rallies(s)
    if not s.rallies:
        raise ToolError("No rallies found, so there is nothing to cut.")
    rallies, segments = pick_segments(s.rallies, video, mode, top_n)
    s.update(message=f"Cutting {len(segments)} rallies...")
    cut_and_concat(video, segments, s.dir / "cut", s.dir / "highlights.mp4")
    length = sum(e - b for b, e in segments)
    title = f"Top {len(rallies)} rallies" if mode == "highlights" else f"All {len(rallies)} rallies"
    s.add_output("highlights", title, "highlights.mp4",
                 f"{length:.0f} s, most shots first" if mode == "highlights" else f"{length:.0f} s, dead time cut")
    return {"video": "highlights.mp4", "rallies": [r.to_dict() for r in rallies], "length_s": round(length, 1)}


def extract_pose(s: Session, stroke: str = "forehand") -> dict:
    """Pose on the best ~8 s: bat hand, stroke type, key moments, joint angles at contact,
    body proportions."""
    from players.body import body_ratios
    from technique import media, pose, strokes
    from technique.pipeline import choose_window, key_moments

    video = s.need_video()
    s.update(message="Reading the pose with MediaPipe...")
    out = s.dir / "pose"
    info = media.probe(video)
    win = choose_window(str(video), info["duration"], 8.0, out, progress=lambda m: None)
    clip = media.make_proxy(video, out / "clip.mp4", height=720, fps=30, start=win["start"], end=win["end"])
    track = pose.extract_pose(clip)
    try:
        pose.require_player(track)
    except pose.NoPlayer as e:
        raise ToolError(str(e)) from e
    side, how = pose.bat_side(clip, track, "auto")
    hits = [h - win["start"] for h in win.get("hit_times", []) if win["start"] <= h <= win["end"]]
    _, p0 = key_moments(track, side, hits, direction="any")
    wing = stroke if stroke in ("forehand", "backhand") else None
    stype, feats = strokes.detect(track, side, p0, wing=wing)
    st = strokes.STROKE_TYPES[stype]
    keys, peak = key_moments(track, side, hits, direction=st.direction, window_s=st.window_s)
    summary = pose.summarize(track, side)
    s.pose = {
        "window_s": [round(win["start"], 2), round(win["end"], 2)], "bat_hand": side, "bat_hand_how": how,
        "stroke_type": stype, "stroke_label": st.label, "stroke_features": feats,
        "key_times_s": [round(k, 2) for k in keys], "at_contact": pose.pose_metrics(track, peak, side),
        "swing_count": summary["swing_count"], "person_visible_ratio": summary["person_visible_ratio"],
        "body": {k: v for k, v in body_ratios(track).items() if k not in ("height_units", "units")},
    }
    return s.pose


class Card(BaseModel):
    title: str = Field(description="Two-word cue, e.g. 'Load low'")
    lines: list[str] = Field(description="Two short lines (<=45 chars): what to look for, then why")
    callouts: list[str] = Field(default_factory=list, description="0-2 tiny ALL-CAPS labels")


def render_breakdown(s: Session, stroke: str = "forehand", stroke_type: str = "", player: str = "",
                     headline: str = "", cards: Optional[list[Card]] = None, recap: str = "",
                     drill: str = "") -> dict:
    """Breakdown video of the user's stroke. With `cards`, the coach's own step text replaces
    the template (the key moments still come from the pose)."""
    from technique import pose
    from technique.pipeline import run_video
    from technique.render import render_breakdown as render
    from technique.schema import StrokeBreakdown

    video = s.need_video()
    out = s.dir / "technique"
    res = run_video(str(video), str(out), stroke or "", player or None, progress=lambda m: s.update(message=m),
                    stroke_type=stroke_type or (s.pose or {}).get("stroke_type"))
    b = StrokeBreakdown.model_validate_json((out / "breakdown.json").read_text())
    if cards:
        for step, card in zip(b.steps, cards):
            card = card if isinstance(card, Card) else Card.model_validate(card)
            step.title, step.lines = card.title, (card.lines + ["", ""])[:2]
            step.callouts, step.highlight_words = card.callouts[:2], []
        b.headline = headline or b.headline
        b.recap = recap or ", ".join(c.title if isinstance(c, Card) else c["title"] for c in cards) + "."
        b.drill = drill or b.drill
        b.source = "coach_writer"
        (out / "breakdown.json").write_text(b.model_dump_json(indent=2))
        s.update(message="Rendering the coach's cards...")
        render(res["outputs"]["clip"], pose.load_track(res["outputs"]["pose_track"]), b,
               str(out / "breakdown.mp4"), res["bat_hand"]["side"])
    shutil.copyfile(out / "breakdown.mp4", s.dir / "breakdown.mp4")
    s.add_output("breakdown", f"{b.stroke_type or b.stroke} breakdown".replace("_", " ").capitalize(),
                 "breakdown.mp4", b.headline)
    s.update(breakdown=json.loads(b.model_dump_json()))
    return {"video": "breakdown.mp4", "headline": b.headline, "steps": [st.title for st in b.steps],
            "recap": b.recap, "drill": b.drill, "analyzer": b.source}


def match_players(s: Session, stroke: str = "forehand", height_cm: Optional[float] = None) -> dict:
    video = s.need_video()
    res = match_video(video, stroke, s.dir / "match", s.dir / "pro_matches.mp4", height_cm,
                      report=lambda p, m: s.update(message=m))
    if res["video"]:
        top = res["matches"][0]
        s.add_output("match", f"You play like {top['name']}", "pro_matches.mp4",
                     ", ".join(f"{m['name']} {m['score']}%" for m in res["matches"]))
    s.update(matches=res["matches"], you=res["you"])
    keys = ("name", "score", "form_score", "differences", "height_cm", "bat_hand", "grip", "warnings")
    return {"matches": [{k: m.get(k) for k in keys} for m in res["matches"]], "you": res["you"]}


TOOLS: dict[str, Callable] = {f.__name__: f for f in
                              (download_url, detect_rallies, cut_highlights, extract_pose, render_breakdown, match_players)}


def make_tools(s: Session) -> dict:
    """LangChain tools bound to this session. Errors come back as text the agent can act on."""
    from langchain_core.tools import tool

    def run(fn: Callable, **kw) -> str:
        try:
            return json.dumps(fn(s, **kw), default=str)
        except (ToolError, dl.LinkError) as e:
            return f"ERROR: {e}"
        except Exception as e:  # keep the agent going; it can try another approach
            return f"ERROR: {type(e).__name__}: {e}"

    @tool
    def download_url(url: str) -> str:
        """Download the user's YouTube link (watch, youtu.be or Shorts; up to 3 minutes) so the
        other tools can use it. Call this first when the user gave a link."""
        return run(TOOLS["download_url"], url=url)

    @tool
    def detect_rallies(threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4) -> str:
        """Find rallies from the sound of ball contact. Returns each rally's start, end, hits and
        shots. Lower threshold or min_hits if nothing is found."""
        return run(TOOLS["detect_rallies"], threshold=threshold, gap=gap, min_hits=min_hits)

    @tool
    def cut_highlights(mode: str = "highlights", top_n: int = 5) -> str:
        """Cut a video of the rallies: mode 'highlights' keeps the top_n rallies by shot count,
        'full' keeps every rally with the dead time removed. The video is shown to the user."""
        return run(TOOLS["cut_highlights"], mode=mode, top_n=top_n)

    @tool
    def extract_pose(stroke: str = "forehand") -> str:
        """Run MediaPipe pose on the best ~8 s of play. Returns bat hand, detected stroke type,
        key moments, joint angles at contact and body proportions. stroke: forehand or backhand."""
        return run(TOOLS["extract_pose"], stroke=stroke)

    @tool
    def render_breakdown(stroke: str = "forehand", stroke_type: str = "", player: str = "",
                         headline: str = "", cards: Optional[list[Card]] = None, recap: str = "",
                         drill: str = "") -> str:
        """Render the vertical coaching video of the user's stroke. Pass exactly 3 `cards`
        (two-word cue title + two short lines) plus headline, recap and drill to use your own
        coaching text; leave them out to use the built-in template. The video is shown to the user."""
        return run(TOOLS["render_breakdown"], stroke=stroke, stroke_type=stroke_type, player=player,
                   headline=headline, cards=cards, recap=recap, drill=drill)

    @tool
    def match_players(stroke: str = "forehand", height_cm: Optional[float] = None) -> str:
        """Find the 3 pros closest to the user (same bat hand, height and body proportions) and
        where their form differs on this stroke (DTW on joint angles). Also makes a video of the
        pros' breakdowns, shown to the user. height_cm is optional."""
        return run(TOOLS["match_players"], stroke=stroke, height_cm=height_cm)

    return {t.name: t for t in (download_url, detect_rallies, cut_highlights, extract_pose,
                                render_breakdown, match_players)}

"""Coach's fixed pipeline: the steps in code, in parallel where they can be, and one Claude
call for the coaching (agent/brief.py). Outputs reach the job page as they finish.

Phase 0 (2026-11-18) timed the deep agent at 242 s and $0.36 on coaching-demo: 19 model calls
(105 s, mostly one after another), full-rate pose on the same 8 s window three times, the
breakdown rendered twice and a vision analyzer whose text the coach then replaced. Here:
  rallies (cached per video) -> highlights in the background
  seed + pose at the hits (cached per video and player) -> the stroke to coach
  a 2.8 s clip of that stroke: pose, height, pro match -> [pros' video in the background]
  one Claude call -> render the coached stroke -> done."""
from __future__ import annotations

import contextvars
import json
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

import numpy as np

import timing
from app import cache

from . import notes
from .tools import TOOLS, Session, ToolError

LEAD, TAIL = 1.5, 0.9      # s of the coached stroke's clip before and after its hit
RENDER_HEIGHT = 1280       # 720x1280 breakdown: 7.9 s to render vs 17.5 s at 1080x1920 (same layout)


def _in_thread(pool: ThreadPoolExecutor, fn: Callable, *args) -> Future:
    """Submit with this thread's context, so the job's timer sees the work."""
    ctx = contextvars.copy_context()
    return pool.submit(ctx.run, fn, *args)


def rally_dicts(rallies: list) -> list[dict]:
    """app.rally.Rally objects -> the dicts hitpose wants (with each rally's hit times)."""
    out = []
    for r in rallies:
        times = np.asarray(r.times if r.times is not None else [], float)
        hits = [float(t) for t in times if r.start - 0.05 <= t <= r.end + 0.05]
        out.append({"start": r.start, "end": r.end, "hits": r.hits, "hit_times": hits})
    return out


def decide_side(hp, hand: str) -> tuple[str, str]:
    """The bat hand from the hit windows: the request's hand, else the wrist that moves at the
    contacts, else red rubber pooled over the scanned rallies, else the faster wrist; Coach
    can't ask, so with no cue it states an assumption (as before)."""
    from technique import hitpose, pose

    if hand in ("left", "right"):
        return hand, "user"
    votes = []   # pose.contact_side's rule, over every probed onset
    for p in hp.probes:
        l, r = p["left"], p["right"]
        if max(l, r) >= hitpose.STROKE_SPEED and max(l, r) > 1.35 * max(min(l, r), .1):
            votes.append(1 if r > l else -1)
    if len(votes) >= 2 and abs(sum(votes)) / len(votes) >= .5:
        return ("right" if sum(votes) > 0 else "left"), "wrist motion near audio contacts"
    lo, hi = sorted(hp.paddle.values())
    if hi > 2000 and hi > 1.8 * max(lo, 1):
        return max(hp.paddle, key=hp.paddle.get), f"paddle colour over several rallies {hp.paddle}"
    body = hitpose.body_track(hp)
    side = pose.dominant_side(body) if body is not None else "unknown"
    if side in ("left", "right"):
        return side, "faster wrist (no decisive contact evidence)"
    return "right", "assumed right-handed: no clear bat-hand cue in this clip"


def run_fixed(s: Session, request: str) -> None:
    from .coach import _files, _progress, plan_from_request

    steps, stroke = plan_from_request(request, s.video is None and bool(s.url))
    keys = {k for k, _ in steps}
    want_reel = "cut_highlights" in keys
    want_stroke = bool(keys & {"extract_pose", "render_breakdown", "match_players"})
    wing = stroke if stroke in ("forehand", "backhand") else None
    noun = wing or "stroke"
    labels = ([("download", "Download the video")] if "download_url" in keys else []) + [("rallies", "Find the rallies")]
    if want_reel:
        labels.append(("reel", "Cut the best rallies"))
    if want_stroke:
        labels += [("pose", f"Track you at your {noun}s"), ("pros", "Find the pros closest to you"),
                   ("coach", "Write the coaching"), ("render", f"Render your {noun}")]
    todos = [{"content": label, "status": "pending"} for _, label in labels]
    index = {k: i for i, (k, _) in enumerate(labels)}
    files: dict[str, str] = {}

    def mark(key: str, state: str, **extra) -> None:
        if key in index:
            todos[index[key]]["status"] = state
        s.update(todos=todos, agentFiles=_files(files), progress=_progress(todos), **extra)

    errors: list[str] = []
    pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="coach")
    background: dict[str, Future] = {}
    reel: list[Future] = []   # the highlight cut, started by the play check
    try:
        if "download" in index:
            mark("download", "in_progress", status="running", message="Downloading the video...")
            TOOLS["download_url"](s, s.url)
            mark("download", "completed")
        video = s.need_video()
        with timing.stage("hash video"):
            key = cache.video_key(video)

        mark("rallies", "in_progress", status="running", message="Listening for ball contacts...")
        with timing.stage("audio hits -> rallies (cached per video)"):
            (raw, min_hits), _ = cache.cached(key, "audio_rallies", lambda: heard(video, s.dir))
        s.rallies = raw   # until the play check below has run

        def play_check() -> list:
            """Keep the rallies that show this table's players in play (pose over every rally,
            39-65 s): only the reel needs it, so it runs beside the stroke analysis."""
            kept, _ = cache.cached(key, "rallies", lambda: play_checked(video, raw, min_hits))
            s.rallies = kept
            if want_reel and kept:
                # Its own job: the coaching call needs the rally count, not the reel (a warm
                # IMG_8782 run waited 12 s for the cut before calling Claude).
                reel.append(_in_thread(pool, TOOLS["cut_highlights"], s))
            return kept

        def rallies_done(kept) -> None:
            """The play check's result, recorded on this thread (the job record and `files`
            are only written from here)."""
            if kept is None:
                return
            files["/rallies.json"] = json.dumps([r.to_dict() for r in kept])
            if want_reel and not kept:
                mark("reel", "completed")
                errors.append("No rallies were heard, so there is no reel. Film closer to the table, with the sound on.")

        background["rallies"] = _in_thread(pool, play_check)
        mark("rallies", "completed")
        if want_reel:
            mark("reel", "in_progress")

        report = facts = None
        if want_stroke:
            mark("pose", "in_progress", message=f"Tracking you at your {noun}s...")
            try:
                facts, clip, track = analyse_stroke(s, video, key, wing, raw)
            except ToolError as e:
                errors.append(str(e))
                facts = None
            mark("pose", "completed")
            if facts is not None:
                mark("pros", "in_progress", message="Comparing you with the pros...")
                try:
                    match = match_pros(s, facts, clip, track, wing or facts["stroke"])
                    facts["closest_pros"] = match["facts"]
                    background["pros_video"] = _in_thread(pool, compile_pros, s, match)
                except Exception as e:
                    traceback.print_exc()
                    errors.append(f"Pro match: {e}")
                mark("pros", "completed")
                mark("coach", "in_progress", message="Writing your coaching...")
                kept = _wait(background.pop("rallies"), errors, "Finding the rallies")
                rallies_done(kept)
                if kept is not None:
                    facts["rallies"] = {"count": len(kept), "longest_shots": max((r.shots for r in kept), default=0),
                                        "reel": "a highlight reel of the top 5 rallies by shot count" if want_reel and kept
                                        else None}
                files["/facts.json"] = json.dumps(facts, indent=1, default=str)   # what the coaching is based on
                report = write_coaching(s, request, facts, clip, track)
                mark("coach", "completed", summary=report.summary,
                     coaching=notes.build(report.summary, fix=report.recap, drill=report.drill))
                mark("render", "in_progress", message=f"Rendering your {noun}...")
                render(s, facts, report, clip, track)
                mark("render", "completed")
        for name, fut in background.items():
            result = _wait(fut, errors, name)
            if name == "rallies":
                rallies_done(result)
        for fut in reel:
            _wait(fut, errors, "Highlight reel")
            mark("reel", "completed")
        summary = report.summary if report else ""
        if errors:
            summary = (summary + "\n\n" if summary else "") + " ".join(errors)
        s.update(status="done", progress=1.0, message="Done.", summary=summary or "Done.",
                 warning=" ".join(errors) or None,   # shown beside the coaching, not inside it
                 todos=[{**t, "status": "completed"} for t in todos], agentFiles=_files(files))
    finally:
        pool.shutdown(wait=False)


# ------------------------------------------------------------------ steps shared with prepare

def heard(video: Path, workdir: Path) -> tuple[list, int]:
    """The audio rallies (and the min_hits they were found with)."""
    from app.rally import detect_rallies as find_rallies

    found = find_rallies(video, workdir, 3.0, 1.6, 4)
    # A quiet video: the same retry the fixed plan made.
    return (found, 4) if found else (find_rallies(video, workdir, 2.5, 1.6, 3), 3)


def play_checked(video: Path, raw: list, min_hits: int) -> list:
    from app.floor_bounce import drop_non_play

    with timing.stage("drop non-play (floor bounce)"):
        return drop_non_play(video, raw, min_hits=min_hits)[0]


def who_key(selection: Optional[tuple], only_me: bool) -> str:
    """The cache key part for whose pose it is."""
    return (f"pick-{selection[0]:.2f}-" + "-".join(f"{v:.3f}" for v in selection[1]) if selection
            else "only-me" if only_me else "auto")


def find_seed(video: Path, selection: Optional[tuple], only_me: bool):
    """The tracker seed: the tapped player; with "Only me", whoever plays the most; else the
    video-wide vote (Session.seed's rule)."""
    from technique import people, pose

    with timing.stage("seed"):
        if selection:
            return pose.identity_from_box(video, *selection)
        seed = people.most_active(str(video)) if only_me else None
        return seed if seed is not None else pose.initial_identity(video)


def prepare(job_id: str, video: str, selection: Optional[tuple] = None, only_me: bool = False,
            who: bool = True) -> None:
    """The worker's prepare lane: fill the per-video cache a Coach job will read, as soon as the
    video is on disk (the job may still be waiting for a slot): audio rallies, seed and pose at
    the strokes (who=False: not known yet, e.g. right after "Which one is you?" got the
    upload), then the play check. The job waits on each entry's lock rather than redo it.
    `video` is a hard link made for this task; it's removed at the end."""
    import tempfile

    from technique import hitpose

    path = Path(video)
    try:
        key = cache.video_key(path)
        with tempfile.TemporaryDirectory() as tmp:
            (raw, min_hits), _ = cache.cached(key, "audio_rallies", lambda: heard(path, Path(tmp)))
        if who:
            w = who_key(selection, only_me)
            seed, _ = cache.cached(key, f"seed-{w}", lambda: find_seed(path, selection, only_me))
            if raw:
                cache.cached(key, f"hitpose-{w}", lambda: hitpose.hit_pose(str(path), rally_dicts(raw), seed))
        cache.cached(key, "rallies", lambda: play_checked(path, raw, min_hits))
    finally:
        if path.parent.name == ".prepare":
            path.unlink(missing_ok=True)


def _wait(fut: Future, errors: list[str], what: str):
    try:
        return fut.result()
    except Exception as e:
        traceback.print_exc()
        errors.append(f"{what}: {e}")
        return None


def analyse_stroke(s: Session, video: Path, key: str, wing: Optional[str], raw: list):
    """Seed, pose at the hits (both cached), the stroke to coach, and a full-rate clip of it.
    Returns the facts for the coaching call, the clip and its pose track."""
    from players.body import body_ratios
    from technique import hitpose, media, pose, strokes
    from technique.pipeline import key_moments

    who = who_key(s.selection, s.only_me)
    seed, _ = cache.cached(key, f"seed-{who}", lambda: find_seed(video, s.selection, s.only_me))
    s.identity = seed
    rallies = rally_dicts(raw)   # the audio rallies: the probes skip any without swings
    if not rallies:
        raise ToolError("No rallies were heard, so we couldn't find your strokes. Keep the sound on.")
    with timing.stage("pose at the hits (cached per video and player)"):
        hp, _ = cache.cached(key, f"hitpose-{who}", lambda: hitpose.hit_pose(str(video), rallies, seed))
    side, how = decide_side(hp, s.hand)
    hitpose.find_own(hp, side)
    best = hitpose.coached(hp, side, wing)
    if best is None:
        raise ToolError("We couldn't see you hitting the ball clearly in the busiest rallies. "
                        "Film with your whole body in view, or tap yourself in 'Which one is you?'.")
    out = s.dir / "pose"
    out.mkdir(parents=True, exist_ok=True)
    start = max(0.0, best.hit - LEAD)
    clip = out / "clip.mp4"

    def coached_clip():
        """The clip's bytes and pose, kept with the video's cache (16.5 s of a warm run)."""
        with timing.stage("clip of the coached stroke (720p)"):
            media.make_proxy(video, clip, height=720, fps=30, start=start, end=best.hit + TAIL)
        with timing.stage("pose on that clip (30 fps)"):
            return clip.read_bytes(), pose.extract_pose(clip, identity=seed)

    (data, track), hit = cache.cached(key, f"clip-{who}-{best.hit:.3f}", coached_clip)
    if hit:
        clip.write_bytes(data)
    pose.require_player(track, picked=s.selection is not None)
    hits = [h - start for r in rallies for h in r["hit_times"] if start <= h <= best.hit + TAIL]
    _, p0 = key_moments(track, side, hits, direction="any")
    st_key, feats = strokes.detect(track, side, p0, wing=wing)
    st = strokes.STROKE_TYPES[st_key]
    times, peak = key_moments(track, side, hits, direction=st.direction, window_s=st.window_s)
    body_src = hitpose.body_track(hp)
    own = [w for w in hp.windows if w.own]
    measured = []
    for w in own:
        m = pose.pose_metrics(w.track, w.peak, side)
        measured.append({"at_s": round(w.hit, 2), **{k: m.get(k) for k in ("elbow_angle_deg", "knee_angle_deg",
                                                                           "stance_width_x_shoulders")}})
    s.update(player={"thumb": pose.player_thumb(clip, track, peak), "picked": s.selection is not None})
    facts = {
        "stroke": st.stroke, "stroke_type": st_key, "stroke_label": st.label,
        "bat_hand": side, "bat_hand_how": how,
        "coached_stroke_at_s": round(best.hit, 2), "key_times_s": [round(t, 2) for t in times],
        "at_contact": pose.pose_metrics(track, peak, side),
        "own_strokes_measured": measured,
        "rallies_scanned": hp.scan, "pose_frames": hp.frames,
        "body": {k: v for k, v in (body_ratios(body_src) if body_src is not None else {}).items()
                 if k not in ("height_units", "units")},
    }
    s.pose = {**facts, "window_s": [round(start, 2), round(best.hit + TAIL, 2)], "peak": int(peak)}
    return facts, clip, track


def match_pros(s: Session, facts: dict, clip: Path, track, stroke: str) -> dict:
    from players.body import angle_curves
    from players.match import match
    from players.table import estimate_height_cm

    side = facts["bat_hand"]
    with timing.stage("height from the table"):
        height = estimate_height_cm(str(clip), track)
    curves = angle_curves(track, side, s.pose["peak"])
    user = {**facts["body"], "height_cm": height["height_cm"] if height else None}
    with timing.stage("match (distance + DTW)"):
        matches = match(user, curves, stroke if stroke in ("forehand", "backhand") else "forehand", side)
    if not matches:
        raise RuntimeError("No pro profiles are built yet. Run: python -m players.build")
    clean = [{k: v for k, v in m.items() if k != "form"} for m in matches]
    s.update(matches=clean, you={"bat_hand": side, "bat_hand_how": facts["bat_hand_how"], "height": height,
                                 "body": facts["body"]})
    keys = ("name", "score", "form_score", "differences", "height_cm", "bat_hand", "grip", "warnings")
    return {"matches": matches, "stroke": stroke, "facts": [{k: m.get(k) for k in keys} for m in clean],
            "height": height}


def compile_pros(s: Session, match: dict) -> None:
    from players.compile import compile_matches

    with timing.stage("compile pros' video"):
        result = compile_matches(match["matches"], match["stroke"], s.dir / "match" / "parts", s.dir / "pro_matches.mp4")
    if result:
        top = match["matches"][0]
        s.add_output("match", f"You play like {top['name']}", "pro_matches.mp4",
                     ", ".join(f"{m['name']} {m['score']}%" for m in match["matches"]))


def _frames_at(clip: Path, times: list[float]) -> list[np.ndarray]:
    import cv2

    cap = cv2.VideoCapture(str(clip))
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
        ok, frame = cap.read()
        if ok:
            out.append(frame)
    cap.release()
    return out


def write_coaching(s: Session, request: str, facts: dict, clip: Path, track):
    """The one Claude call; without a key (or if it fails) the offline template writes the cards."""
    import os

    from . import brief

    frames = _frames_at(clip, facts["key_times_s"])
    labelled = list(zip(["preparation", "contact", "finish"], frames))
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            report, model = brief.write(request, facts, labelled)
            s.update(engine="pipeline", engineNote=f"fixed pipeline + one {model} call")
            return report
        except Exception as e:
            traceback.print_exc()
            s.update(engineNote=f"the coaching call failed ({type(e).__name__}); offline cards")
    else:
        s.update(engine="pipeline", engineNote="fixed pipeline, no ANTHROPIC_API_KEY: offline cards")
    return offline_report(facts, clip, track)


def offline_report(facts: dict, clip: Path, track):
    """The offline analyzer's breakdown, as a report (no Claude)."""
    from technique.analyze import OfflineAnalyzer

    from .brief import Card, CoachReport

    b = OfflineAnalyzer().from_video(str(clip), facts["stroke"], facts["key_times_s"], {}, facts["key_times_s"],
                                     None, contact_metrics=facts["at_contact"], stroke_type=facts["stroke_type"],
                                     detected=True)
    cards = [Card(moment=m, title=st.title, lines=(st.lines + ["", ""])[:2], callouts=st.callouts[:2])
             for m, st in zip(["preparation", "contact", "finish"], b.steps)]
    pros = facts.get("closest_pros") or []
    c = facts["at_contact"]
    seen = [f"{name} about {c[k]}°" for name, k in (("elbow", "elbow_angle_deg"), ("knees", "knee_angle_deg"))
            if c.get(k) is not None]
    opening = " ".join(filter(None, [
        f"Your {facts['stroke_label'].lower()}, measured at contact: {', '.join(seen)}." if seen
        else f"Your {facts['stroke_label'].lower()}.",
        f"You play most like {pros[0]['name']} ({pros[0]['score']}% body match)." if pros else ""]))
    fixes = "\n".join(f"{i}. **{card.title.capitalize()}.** {' '.join(x for x in card.lines if x)}"
                      for i, card in enumerate(cards, 1))
    summary = "\n\n".join(filter(None, [opening, f"**What to work on first:**\n{fixes}" if cards else "",
                                       f"**Drill:** {b.drill}" if b.drill else ""]))
    return CoachReport(summary=summary, headline=b.headline, stroke_type=facts["stroke_type"], grip=b.grip,
                       stance=b.stance, swing_path=b.swing_path, contact_point=b.contact_point,
                       follow_through=b.follow_through, cards=cards, recap=b.recap or "", drill=b.drill or "")


def render(s: Session, facts: dict, report, clip: Path, track) -> None:
    """The breakdown video of the coached stroke only, from its 2.8 s clip."""
    import json
    import shutil

    from technique.render import render_breakdown
    from technique.schema import Step, StrokeBreakdown

    steps = [Step(title=c.title, lines=(c.lines + ["", ""])[:2], highlight_words=[], key_time_s=t,
                  callouts=c.callouts[:2]) for c, t in zip(report.cards, facts["key_times_s"])]
    b = StrokeBreakdown(stroke=facts["stroke"], stroke_type=report.stroke_type or facts["stroke_type"],
                        handedness=facts["bat_hand"], headline=report.headline, grip=report.grip,
                        stance=report.stance, swing_path=report.swing_path, contact_point=report.contact_point,
                        follow_through=report.follow_through, steps=steps, recap=report.recap, drill=report.drill,
                        source="coach")
    out = s.dir / "technique"
    out.mkdir(parents=True, exist_ok=True)
    (out / "breakdown.json").write_text(b.model_dump_json(indent=2))
    with timing.stage("render"):
        render_breakdown(str(clip), track, b, str(out / "breakdown.mp4"), facts["bat_hand"],
                         height=RENDER_HEIGHT, preset="superfast")
    shutil.copyfile(out / "breakdown.mp4", s.dir / "breakdown.mp4")
    s.add_output("breakdown", f"{b.stroke_type or b.stroke} breakdown".replace("_", " ").capitalize(),
                 "breakdown.mp4", b.headline)
    s.update(breakdown=json.loads(b.model_dump_json()))

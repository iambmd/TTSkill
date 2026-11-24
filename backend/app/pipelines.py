"""Plain (non-agent) pipelines. The deepagents wrapper will call these same steps as tools."""
from __future__ import annotations

import json
import shutil
import time
import traceback
from pathlib import Path
from typing import Callable

import timing
from limits import LIMITS
from messages import Msg, say

from . import jobs
from .cut import cut_and_concat, cut_segment, duration, padded_segments, thumbnail
from .download import download
from .rally import detect_rallies


def fetch_then(job_id: str, url: str, run: Callable[..., None], *args, **kwargs) -> None:
    """Downloads a pasted link into the job folder as the upload would be, runs the normal
    pipeline on it, then deletes the full download (the result video stays)."""
    seen = {"pct": -1}

    def report(f: float) -> None:
        pct = int(f * 100)
        if pct >= seen["pct"] + 5:  # yt-dlp reports many times a second
            seen["pct"] = pct
            jobs.update(job_id, progress=round(0.05 * f, 3), **say("progress.downloadingPct", pct=pct))

    try:
        stage = {"autocutStage": {"key": "preparing"}} if run is run_autocut else {}
        jobs.update(job_id, status="running", progress=0.0, **say("progress.downloading"), **stage)
        path = download(url, jobs.job_dir(job_id), progress=report)
    except Exception as exc:  # LinkError messages are written for the user
        traceback.print_exc()
        jobs.fail(job_id, exc, "We couldn't open this video. Try another link or upload a file.")
        return
    try:
        run(job_id, path, *args, **kwargs)
    finally:
        path.unlink(missing_ok=True)


def pick_segments(found: list, video: Path, mode: str, top_n: int, total: float | None = None) -> tuple[list, list[tuple[float, float]]]:
    """Rallies to keep and their padded segments. Highlights: best rallies first, padding
    never merges them so each stays its own clip. Full: every rally, overlaps merged."""
    rallies = sorted(found, key=lambda r: -r.hits)[:top_n] if mode == "highlights" else found
    total = duration(video) if total is None else total
    return rallies, padded_segments([(r.start, r.end) for r in rallies], total,
                                    merge=mode != "highlights",
                                    bounds=[r.clip_bounds or (0.0, total) for r in rallies])


def few_rallies_msg(count: int) -> Msg | None:
    """Advice when the sound gave fewer rallies than a useful cut needs (shared/limits.json)."""
    if count >= LIMITS["autocut"]["min_rallies"]:
        return None
    return (Msg("progress.autocut.heardNone") if count == 0 else Msg("progress.autocut.heardOne") if count == 1
            else Msg("progress.autocut.heardFew", n=count))


def few_rallies_warning(count: int) -> str | None:
    m = few_rallies_msg(count)
    return str(m) if m else None


def run_autocut(job_id: str, video: Path, mode: str, top_n: int, threshold: float, gap: float, min_hits: int) -> None:
    started = time.monotonic()
    estimate = 0.0

    def report(key: str, progress: float, done: int | None = None, total: int | None = None, **fields) -> None:
        elapsed = time.monotonic() - started
        # Start with a duration-based guess and blend in the measured pace as work advances.
        measured = elapsed / max(progress, 0.1)
        expected = estimate * (1 - progress) + measured * progress
        eta = max(1, round(expected - elapsed))
        stage = {"key": key, "etaUntil": round(time.time()) + eta}
        if total:
            stage.update(done=done, total=total)
        jobs.update(job_id, status="running", progress=round(progress, 3), autocutStage=stage, **fields)

    try:
        video_seconds = duration(video)
        estimate = 12 + 0.35 * video_seconds
        workdir = jobs.job_dir(job_id)
        report("extracting_audio", 0.06)
        found = detect_rallies(video, workdir, threshold, gap, min_hits, lambda: report("finding_rallies", 0.12))
        if found:
            from .floor_bounce import drop_non_play  # heavy imports (MediaPipe, OpenCV)

            def reviewed(done: int, total: int) -> None:
                report("finding_rallies", 0.18 + 0.44 * done / total, done, total)

            reviewed(0, len(found))
            found, bounces = drop_non_play(video, found, min_hits=min_hits, progress=reviewed)
            if bounces:
                print(f"dropped {len(bounces)} non-play spans: {[r.to_dict() for r in bounces]}")
        few = few_rallies_msg(len(found))  # counted after non-play spans are dropped
        warning = few.fields("warning") if few else {"warning": None}
        if not found:
            jobs.update(job_id, status="done", progress=1.0, rallies=[], **warning,
                        autocutStage={"key": "done"}, **say("progress.autocut.none"))
            return
        report("ranking", 0.68)
        rallies, segments = pick_segments(found, video, mode, top_n, total=video_seconds)
        # Full cuts merge overlapping padding. Keep individual clips as well for editing
        # and coaching, reusing the rendered parts wherever they are already separate.
        separate = len(segments) != len(rallies)
        card_spans = padded_segments(
            [(r.start, r.end) for r in rallies], video_seconds, merge=False,
            bounds=[r.clip_bounds or (0.0, video_seconds) for r in rallies],
        ) if separate else segments
        extra = len(card_spans) if separate else 0
        render_total = len(segments) + extra
        clips: list[dict] = []
        report("rendering", 0.72, 0, render_total, rallies=[r.to_dict() for r in rallies])

        def publish(i: int, path: Path) -> None:
            start, end = card_spans[i - 1]
            name = f"rally-{i}"
            public = workdir / f"{name}.mp4"
            if path != public:
                public.hardlink_to(path)
            thumb = f"{name}.jpg"
            thumbnail(public, workdir / thumb)
            base = f"/jobs/{job_id}/files"
            clips.append({"id": i, "start": start, "end": end, "clipUrl": f"{base}/{public.name}",
                          "thumbnailUrl": f"{base}/{thumb}"})
            if i == 1:
                jobs.update(job_id, previewUrl=clips[0]["clipUrl"])

        if separate:
            for i, span in enumerate(card_spans, 1):
                publish(i, cut_segment(video, span, workdir / f"rally-{i}.mp4"))
                report("rendering", 0.72 + 0.25 * i / render_total, i, render_total)

        def rendered(done: int, _: int, path: Path) -> None:
            if not separate:
                publish(done, path)
            completed = extra + done
            report("rendering", 0.72 + 0.25 * completed / render_total, completed, render_total)

        cut_and_concat(video, segments, workdir, workdir / "result.mp4", clip_ready=rendered)
        length = sum(e - s for s, e in segments)
        done = "progress.autocut.doneTop" if mode == "highlights" else "progress.autocut.doneAll"
        jobs.update(job_id, status="done", progress=1.0, resultUrl=f"/jobs/{job_id}/result", **warning,
                    autocutStage={"key": "done"}, rallyClips=clips, **say(done, n=len(rallies), seconds=f"{length:.0f}"))
    except Exception as exc:
        traceback.print_exc()
        jobs.fail(job_id, exc, Msg("progress.autocut.failed"))


# Each technique pipeline log line: how far along it is, and what the page says meanwhile. The
# log lines are for developers ("window 54.0-60.2s (rally)"); the page shows the stage.
_STAGES = [("starting", 0.05, "start"), ("only me", 0.05, "onlyMe"), ("input", 0.1, "reading"),
           ("longest rally", 0.2, "finding"), ("no rallies", 0.2, "finding"), ("player", 0.2, "finding"),
           ("rally", 0.2, "finding"), ("window", 0.25, "finding"), ("running MediaPipe", 0.35, "pose"),
           ("bat hand", 0.5, "hand"), ("stroke type", 0.55, "strokeType"), ("analysing", 0.6, "analysing"),
           ("rendering", 0.8, "rendering"), ("done", 0.95, "finishing")]


def _progress(job_id: str):
    state = {"p": 0.05}

    def report(msg: str) -> None:
        print(f"[{job_id[:8]}] {msg}", flush=True)
        for prefix, p, stage in _STAGES:
            if msg.startswith(prefix):
                state["p"] = max(state["p"], p)
                jobs.update(job_id, status="running", progress=state["p"], **say(f"progress.breakdown.{stage}"))
                return
        jobs.update(job_id, status="running", progress=state["p"])   # a detail line: keep the stage text
    return report


def run_breakdown(job_id: str, video: Path | None, text: str, stroke: str, player: str,
                  hand: str = "auto", stroke_type: str = "", selection: tuple | None = None,
                  only_me: bool = False, lang: str = "en") -> None:
    """Runs backend/technique and copies its breakdown.mp4 to result.mp4 for the job page.
    lang: the language the step cards, drill, video prompt and video labels are written in."""
    try:
        from technique.pipeline import run_text, run_video  # heavy imports (MediaPipe, OpenCV)
        from technique.strokes import label

        out = jobs.job_dir(job_id) / "technique"
        report = _progress(job_id)
        report("starting technique pipeline")
        if video is not None:
            # The player the user tapped; with "Only me in the video", whoever plays the most;
            # otherwise the video-wide seed.
            from technique import people, pose
            if selection:
                seed = pose.identity_from_box(video, *selection)
            elif only_me:
                report("only me in the video: finding who plays the most")
                seed = people.most_active(str(video))
            else:
                seed = None
            res = run_video(str(video), str(out), stroke, player or None, progress=report, hand=hand,
                            stroke_type=stroke_type or None, identity=seed, picked=bool(selection), lang=lang)
        else:
            res = run_text(text, str(out), stroke, player or None, progress=report,
                           stroke_type=stroke_type or None, lang=lang)
        overlay = Path(res["outputs"]["overlay_video"])
        shutil.copyfile(overlay, jobs.job_dir(job_id) / "result.mp4")
        breakdown = json.loads((out / "breakdown.json").read_text())
        prompt_path = out / "video_prompt.json"
        video_prompt = json.loads(prompt_path.read_text()) if prompt_path.exists() else None
        jobs.update(job_id, status="done", progress=1.0,
                    **say("progress.breakdown.done", headline=breakdown.get("headline") or Msg("progress.breakdown.ready"),
                          analyzer=res["analyzer"]),
                    resultUrl=f"/jobs/{job_id}/result", breakdown=breakdown,
                    videoPrompt=video_prompt, analyzer=res["analyzer"],
                    batHand=res.get("bat_hand"), window=res.get("window"),
                    player={"thumb": res.get("player_thumb"), "picked": bool(selection)},
                    strokeType={"key": res.get("stroke_type"), "label": label(res.get("stroke_type") or res["stroke"]),
                                "detected": res.get("stroke_type_detected") is not None,
                                "features": res.get("stroke_type_detected")})
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.fail(job_id, exc)


def match_video(video: Path, stroke: str, out: Path, dest: Path, height_cm: float | None = None,
                hand: str = "auto", report: Callable[[float, Msg], None] = lambda p, m: None,
                grip: str | None = None, chosen: dict | None = None, identity=None,
                picked: bool = False, lang: str = "en") -> dict:
    """Find my pro match core, shared by the /jobs/match pipeline and the coach agent:
    pose on the user's clip, body profile, height (entered or from the table), top 3 pros
    with the same bat hand (and grip first, when given), form differences, and one
    compiled video at `dest`. report(progress, Msg). lang: the language of the differences,
    warnings and the video's title cards."""
    from players.body import angle_curves, body_ratios
    from players.compile import compile_matches
    from players.match import match
    from players.table import estimate_height_cm
    from technique import media, pose
    from technique.pipeline import choose_window, key_moments

    out.mkdir(parents=True, exist_ok=True)
    report(0.1, Msg("progress.match.swings"))
    info = media.probe(video)
    # Same video-wide player seed as Breakdown and Coach, then fixed appearance tracking.
    # Coach passes the window and seed its pose step already chose (`chosen`, `identity`).
    if identity is None:
        with timing.stage("seed (initial_identity)"):
            identity = pose.initial_identity(video)
    with timing.stage("choose_window"):
        win = chosen or choose_window(str(video), info["duration"], 8.0, out, progress=lambda m: None,
                                      identity=identity)
    with timing.stage("proxy 720p"):
        clip = media.make_proxy(video, out / "clip.mp4", height=720, fps=30, start=win["start"], end=win["end"])
    report(0.3, Msg("progress.match.reading"))
    with timing.stage("pose (MediaPipe, full rate)"):
        track = pose.extract_pose(clip, identity=identity)
    pose.require_player(track, picked=picked)
    hits = [h - win["start"] for h in win.get("hit_times", []) if win["start"] <= h <= win["end"]]
    with timing.stage("bat_side"):
        side, how = pose.bat_side(clip, track, hand, hit_times=hits, pooled=win.get("paddle"))
    _, contact = key_moments(track, side, hits, direction="up")
    body = body_ratios(track)
    curves = angle_curves(track, side, contact)
    if height_cm:
        height = {"height_cm": round(height_cm), "method": "entered"}
    else:
        report(0.55, Msg("progress.match.height"))
        with timing.stage("height from the table"):
            height = estimate_height_cm(str(clip), track)
    user = {**body, "height_cm": height["height_cm"] if height else None}
    report(0.65, Msg("progress.match.pros"))
    with timing.stage("match (distance + DTW)"):
        matches = match(user, curves, stroke, side, grip=grip, lang=lang)
    if not matches:
        raise RuntimeError("No pro profiles are built yet. Run: python -m players.build")
    report(0.75, Msg("progress.match.compile"))
    with timing.stage("compile pros' video"):
        result = compile_matches(matches, stroke, out / "parts", dest, lang=lang)
    return {"matches": [{k: v for k, v in m.items() if k != "form"} for m in matches],
            "you": {"bat_hand": side, "bat_hand_how": how, "height": height,
                    "body": {k: v for k, v in body.items() if k not in ("height_units", "units")}},
            "video": str(result) if result else None,
            "player_thumb": pose.player_thumb(clip, track, contact)}


def run_match(job_id: str, video: Path, stroke: str, height_cm: float | None = None,
              hand: str = "auto", grip: str | None = None, selection: tuple | None = None,
              lang: str = "en") -> None:
    """lang: the language of the pros' differences, warnings and the video's title cards."""
    try:
        jobs.update(job_id, status="running", progress=0.05, **say("progress.starting"))
        seed = None
        if selection:
            from technique import pose
            seed = pose.identity_from_box(video, *selection)
        res = match_video(video, stroke, jobs.job_dir(job_id) / "match", jobs.job_dir(job_id) / "result.mp4",
                          height_cm, hand, report=lambda p, m: jobs.update(job_id, progress=p, **m.fields()),
                          grip=grip, identity=seed, picked=bool(selection), lang=lang)
        top = res["matches"][0]
        jobs.update(job_id, status="done", progress=1.0,
                    **say("progress.match.done", name=top["name"], score=top["score"]),
                    resultUrl=f"/jobs/{job_id}/result" if res["video"] else None,
                    matches=res["matches"], you=res["you"],
                    player={"thumb": res.get("player_thumb"), "picked": bool(selection)})
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.fail(job_id, exc)

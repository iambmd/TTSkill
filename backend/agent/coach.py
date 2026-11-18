"""TT Coach: a LangChain deep agent (Claude) for one request about one video.

The main agent plans with the deepagents todo list, keeps its plan and notes in the
virtual file system (/plan.md, /rallies.json, /pose_summary.json, /matches.json), and
delegates to three subagents:
  * clip_analyst   - rallies, highlight reels and pose (detect_rallies, cut_highlights, extract_pose)
  * player_matcher - closest pros and form differences (match_players)
  * coach_writer   - step cards in the swift_style.json style, rendered (render_breakdown)
The todo list and files stream into the job record, so the /coach page shows the plan
updating live. Without ANTHROPIC_API_KEY, or if the agent fails, the same tools run in a
fixed plan built from the request (same live todo list), so the demo always finishes."""
from __future__ import annotations

import json
import os
import re
import traceback
from pathlib import Path
from typing import Optional

from technique import style

from .tools import TOOLS, Session, make_tools

MODEL = os.environ.get("COACH_MODEL", "claude-opus-5-5")

SYSTEM = """You are TT Coach, a table tennis coach working on one user's video. Your tools run real
video pipelines; each call takes 10-60 seconds, so never run the same one twice.

How to work:
1. First call write_todos with a short plan (3-6 items) for exactly what the user asked.
2. Save the plan to /plan.md with write_file.
3. If the user gave a link and no video is loaded, call download_url before anything else.
4. Delegate with the task tool:
   - clip_analyst: rallies, highlight reels and pose measurements. Ask it to save /rallies.json
     and /pose_summary.json.
   - player_matcher: the pros closest to the user and where their form differs. It saves /matches.json.
   - coach_writer: the 3 coaching cards and the breakdown video of the user's stroke.
5. Mark each todo done as it finishes. Keep short notes in /notes.md.
6. End with a short answer to the user: what you made and the 2-3 things to work on first.
   The videos are already on their screen, so don't paste paths or links.
Only do what was asked. If a tool returns ERROR, adjust once (for example lower the rally
threshold) and otherwise explain the problem plainly."""

CLIP_ANALYST = """You analyse a table tennis video. Use detect_rallies and cut_highlights for rallies and
highlight reels, and extract_pose for body and swing measurements (pass the stroke the user
cares about). Save what you measured with write_file: /rallies.json (rally list) and
/pose_summary.json (the extract_pose result). Reply with a 3-5 line summary of the numbers
that matter for coaching."""

PLAYER_MATCHER = """You find the pros closest to the user with match_players (bat hand, height, body
proportions, and DTW on the stroke's joint angles). Save the result to /matches.json with
write_file and reply with the top 3, their scores and the form differences."""

COACH_WRITER = """You write the coaching cards and render the user's breakdown video. First read
/pose_summary.json and /matches.json if they exist (read_file), so the cards fix what the
measurements show. Then call render_breakdown once with: stroke, stroke_type (from the pose
summary), a headline (3-6 words), exactly 3 cards in time order, a recap line and one drill.
Save the cards to /cards.md. Reply with the cards."""


# ------------------------------------------------------------------ deep agent

FILE_TOOLS = ["ls", "read_file", "write_file", "edit_file"]  # virtual file system only, no shell


def build_agent(s: Session, model=None):
    from deepagents import FilesystemMiddleware, create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware
    from langchain_anthropic import ChatAnthropic

    t = make_tools(s)
    # "default" fallbacks retry a declined request on Anthropic's recommended model server-side.
    model = model or ChatAnthropic(model=MODEL, max_tokens=16000,
                                   betas=["server-side-fallback-2026-07-01"], model_kwargs={"fallbacks": "default"})
    subagents = [
        {"name": "clip_analyst", "system_prompt": CLIP_ANALYST,
         "description": "Finds rallies, cuts highlight reels and measures the player's pose and swing in the user's video.",
         "tools": [t["download_url"], t["detect_rallies"], t["cut_highlights"], t["extract_pose"]],
         "middleware": [FilesystemMiddleware(tools=FILE_TOOLS)]},
        {"name": "player_matcher", "system_prompt": PLAYER_MATCHER,
         "description": "Finds the 3 pros closest to the user's build and bat hand, and where the user's form differs.",
         "tools": [t["match_players"]], "middleware": [FilesystemMiddleware(tools=FILE_TOOLS)]},
        {"name": "coach_writer", "system_prompt": COACH_WRITER + "\n\n" + style.prompt_guide(),
         "description": "Writes 3 coaching cards in the house style and renders the user's breakdown video.",
         "tools": [t["render_breakdown"]], "middleware": [FilesystemMiddleware(tools=FILE_TOOLS)]},
    ]
    # The todo list (write_todos) is the plan the /coach page shows live; the default
    # filesystem middleware is replaced by one without the shell tool.
    return create_deep_agent(model=model, tools=list(t.values()), system_prompt=SYSTEM, subagents=subagents,
                             middleware=[TodoListMiddleware(), FilesystemMiddleware(tools=FILE_TOOLS)],
                             name="tt_coach")


def _file_text(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        c = v.get("content", "")
        return "\n".join(c) if isinstance(c, list) else str(c)
    return str(v)


def _files(files: dict) -> list[dict]:
    return [{"name": k, "preview": _file_text(v)[:1200]} for k, v in sorted(files.items())]


def _todos(todos: list) -> list[dict]:
    return [{"content": t.get("content", ""), "status": t.get("status", "pending")} for t in todos or []]


def _progress(todos: list[dict]) -> float:
    if not todos:
        return 0.05
    done = sum(t["status"] == "completed" for t in todos) + 0.5 * sum(t["status"] == "in_progress" for t in todos)
    return round(min(0.95, 0.05 + 0.9 * done / len(todos)), 3)


def _text(msg) -> str:
    c = getattr(msg, "content", "")
    if isinstance(c, list):
        return "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return str(c)


def run_agent(s: Session, request: str, model=None) -> None:
    agent = build_agent(s, model)
    where = (f"The user's video is uploaded and loaded." if s.video else
             f"The user's video link: {s.url} (call download_url first).")
    state: dict = {}
    for state in agent.stream({"messages": [{"role": "user", "content": f"{request}\n\n{where}"}]},
                              stream_mode="values", config={"recursion_limit": 120}):
        todos = _todos(state.get("todos"))
        s.update(status="running", todos=todos, agentFiles=_files(state.get("files") or {}),
                 progress=_progress(todos))
    final = next((_text(m) for m in reversed(state.get("messages", [])) if m.type == "ai" and _text(m)), "")
    s.update(status="done", progress=1.0, summary=final, message="Done.",
             todos=[{**t, "status": "completed"} for t in _todos(state.get("todos"))])


# ------------------------------------------------------------------ fallback

def hand_from_request(request: str) -> str:
    """The bat hand when the user states it ("I'm left-handed", "lefty"); otherwise auto."""
    t = request.lower()
    if re.search(r"\bleft[- ]?hand(ed|er)?\b|\blefty\b|\bleftie\b", t):
        return "left"
    if re.search(r"\bright[- ]?hand(ed|er)?\b|\brighty\b", t):
        return "right"
    return "auto"


def plan_from_request(request: str, has_link: bool) -> tuple[list[tuple[str, str]], str]:
    t = request.lower()
    stroke = "backhand" if "backhand" in t else "forehand" if "forehand" in t else "auto"
    rallies = any(w in t for w in ("rall", "highlight", "best point", "best shot", "dead time", "cut ", "points"))
    tech = any(w in t for w in ("fix", "technique", "form", "forehand", "backhand", "stroke", "swing",
                                "improve", "coach", "breakdown", "serve", "loop"))
    pros = any(w in t for w in (" pro", "pros", "who do i", "play like", "similar", "compare"))
    if not (rallies or tech or pros):
        rallies = tech = True
    noun = "stroke" if stroke == "auto" else stroke  # "auto" is a setting, not something to say
    steps = [("download_url", "Download the video")] if has_link else []
    if rallies:
        steps += [("detect_rallies", "Find the rallies"), ("cut_highlights", "Cut the best rallies")]
    if tech or pros:
        steps.append(("extract_pose", f"Measure your {noun} with MediaPipe"))
    if pros:
        steps.append(("match_players", f"Find the pros closest to your {noun}"))
    if tech:
        steps.append(("render_breakdown", f"Write the coaching cards and render your {noun}"))
    steps.append(("summary", "Sum up what to work on"))
    return steps, stroke


def run_fallback(s: Session, request: str, why: str) -> None:
    steps, stroke = plan_from_request(request, s.video is None and bool(s.url))
    todos = [{"content": label, "status": "pending"} for _, label in steps]
    files = {"/plan.md": "# Plan\n" + "\n".join(f"{i}. {label}" for i, (_, label) in enumerate(steps, 1))
             + f"\n\nRequest: {request}\nEngine: fixed plan ({why})"}
    results: dict = {}

    def push(**extra) -> None:
        s.update(todos=todos, agentFiles=_files(files), progress=_progress(todos), **extra)

    for i, (key, label) in enumerate(steps):
        todos[i]["status"] = "in_progress"
        push(status="running", message=label + "...")
        try:
            if key == "download_url":
                results[key] = TOOLS[key](s, s.url)
            elif key == "detect_rallies":
                r = TOOLS[key](s)
                if not r["count"]:
                    r = TOOLS[key](s, threshold=2.5, min_hits=3)
                results[key] = r
                files["/rallies.json"] = json.dumps(r["rallies"], indent=2)
            elif key == "cut_highlights":
                results[key] = TOOLS[key](s) if results.get("detect_rallies", {}).get("count") else None
            elif key in ("extract_pose", "match_players"):
                results[key] = TOOLS[key](s, stroke=stroke)
                if key == "extract_pose" and stroke == "auto":
                    from technique.strokes import STROKE_TYPES
                    detected = STROKE_TYPES.get(results[key].get("stroke_type", ""))
                    if detected and detected.stroke in ("forehand", "backhand"):
                        stroke = detected.stroke
                files["/pose_summary.json" if key == "extract_pose" else "/matches.json"] = json.dumps(
                    results[key], indent=2, default=str)
            elif key == "render_breakdown":
                results[key] = TOOLS[key](s, stroke=stroke)
                files["/cards.md"] = "\n".join([results[key]["headline"], *results[key]["steps"],
                                                results[key]["recap"] or "", results[key]["drill"] or ""])
        except Exception as e:
            traceback.print_exc()
            results[key] = {"error": str(e)}
            files.setdefault("/notes.md", "")
            files["/notes.md"] += f"- {label}: {e}\n"
        todos[i]["status"] = "completed"
        push()
    summary = _summary(results, stroke)
    files["/notes.md"] = files.get("/notes.md", "") + summary
    s.update(status="done", progress=1.0, summary=summary, message="Done.", todos=todos, agentFiles=_files(files))


def _summary(r: dict, stroke: str) -> str:
    lines = []
    dr, ch = r.get("detect_rallies"), r.get("cut_highlights")
    if dr and "count" in dr:
        n = dr["count"]
        found = f"I found {n} {'rally' if n == 1 else 'rallies'}"
        if ch and len(ch["rallies"]) > 1:
            found += f" and cut the best {len(ch['rallies'])} into a {ch['length_s']:.0f} s reel."
        elif ch:
            found += f" and cut it into a {ch['length_s']:.0f} s clip."
        lines.append(found if found.endswith(".") else found + ".")
    pz = r.get("extract_pose")
    if pz and "at_contact" in pz:
        c = pz["at_contact"]
        seen = [f"elbow about {c['elbow_angle_deg']}°" if c.get("elbow_angle_deg") is not None else "",
                f"knees about {c['knee_angle_deg']}°" if c.get("knee_angle_deg") is not None else ""]
        seen = [x for x in seen if x]
        stance = c.get("stance_width_x_shoulders")
        lines.append(f"Your {pz['stroke_label'].lower()}: " + (" and ".join(seen) + " at contact" if seen
                     else "your joints weren't all in frame at contact")
                     + (f", stance {stance}x shoulder width." if stance is not None else "."))
        if str(pz.get("bat_hand_how", "")).startswith("assumed"):
            hand = pz.get("bat_hand", "right")
            other = "left" if hand == "right" else "right"
            lines.append(f"I couldn't see which hand holds your bat, so I assumed {hand}-handed. "
                         f"If you play {other}-handed, say so in your request.")
    mp = r.get("match_players")
    if mp and mp.get("matches"):
        top = mp["matches"][0]
        lines.append(f"You play most like {top['name']} ({top['score']}% body match)."
                     + (f" {top['differences'][0]}" if top.get("differences") else ""))
    rb = r.get("render_breakdown")
    if rb and "steps" in rb:
        lines.append(f"Work on: {rb['recap']} Then: {rb['drill']}")
    errs = [f"{k}: {v['error']}" for k, v in r.items() if isinstance(v, dict) and "error" in v]
    if errs:
        lines.append("Some steps failed: " + "; ".join(errs))
    return " ".join(lines) or f"I couldn't analyse the {'stroke' if stroke == 'auto' else stroke} in this video."


# ------------------------------------------------------------------ entry point

def run_coach(job_id: str, video: Optional[Path], url: Optional[str], request: str,
              selection: Optional[tuple] = None, only_me: bool = False) -> None:
    """Background job: the deep agent when a key is set, the fixed plan otherwise or on failure."""
    s = Session(job_id, video=video, url=url, hand=hand_from_request(request), selection=selection,
                only_me=only_me)
    s.update(status="running", progress=0.02, message="Planning...", todos=[], outputs=[])
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            s.update(engine="deepagents")
            run_agent(s, request)
            return
        except Exception as e:
            traceback.print_exc()
            why = f"the agent stopped: {type(e).__name__}"
            s.update(agentError=str(e)[:300])
    else:
        why = "no ANTHROPIC_API_KEY"
    s.update(engine="fallback", engineNote=why)
    try:
        run_fallback(s, request, why)
    except Exception as e:
        traceback.print_exc()
        s.update(status="failed", message=str(e))

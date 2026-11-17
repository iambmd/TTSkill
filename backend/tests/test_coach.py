"""TT Coach: the deep agent's live todo list and files reach the job record (scripted fake
model, no network), and the no-key fallback runs the same tools in a plan from the request."""
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import coach, tools
from app import jobs


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


def _call(name, args, i):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


def test_agent_streams_todos_files_and_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    job = jobs.create("coach", {})
    todos = [{"content": "Find the rallies", "status": "in_progress"}, {"content": "Fix the forehand", "status": "pending"}]
    script = iter([
        _call("write_todos", {"todos": todos}, 1),
        _call("write_file", {"file_path": "/plan.md", "content": "1. rallies\n2. forehand"}, 2),
        _call("detect_rallies", {}, 3),   # no video yet: the tool answers with an ERROR the agent can read
        AIMessage(content="Here is what I found."),
    ])
    s = tools.Session(job["id"])
    coach.run_agent(s, "show my best rallies", model=ScriptedModel(messages=script))
    done = jobs.load(job["id"])
    assert done["status"] == "done" and done["summary"] == "Here is what I found."
    assert [t["content"] for t in done["todos"]] == ["Find the rallies", "Fix the forehand"]
    assert all(t["status"] == "completed" for t in done["todos"])
    assert any(f["name"] == "/plan.md" and "rallies" in f["preview"] for f in done["agentFiles"])


def test_plan_from_request():
    steps, stroke = coach.plan_from_request("here's my match, show my best rallies and fix my backhand", True)
    keys = [k for k, _ in steps]
    assert stroke == "backhand"
    assert keys == ["download_url", "detect_rallies", "cut_highlights", "extract_pose", "render_breakdown", "summary"]
    keys = [k for k, _ in coach.plan_from_request("which pros do I play like?", False)[0]]
    assert "match_players" in keys and "detect_rallies" not in keys


def test_fallback_runs_tools_with_a_live_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    job = jobs.create("coach", {})
    calls = []

    def fake(name, result):
        def f(s, *a, **k):
            calls.append(name)
            assert jobs.load(s.job_id)["todos"][len(calls) - 1]["status"] == "in_progress"
            return result
        return f

    monkeypatch.setitem(tools.TOOLS, "detect_rallies", fake("detect_rallies", {"count": 3, "rallies": [{"shots": 4}]}))
    monkeypatch.setitem(tools.TOOLS, "cut_highlights", fake("cut_highlights", {"rallies": [1, 2], "length_s": 20.0}))
    monkeypatch.setitem(tools.TOOLS, "extract_pose", fake("extract_pose", {
        "stroke_label": "Forehand topspin", "at_contact": {"elbow_angle_deg": 110, "knee_angle_deg": 140,
                                                           "stance_width_x_shoulders": 1.8}}))
    monkeypatch.setitem(tools.TOOLS, "render_breakdown", fake("render_breakdown", {
        "headline": "h", "steps": ["Load low", "Lift through", "End high"], "recap": "Load low, lift through, end high.",
        "drill": "Shadow 20 swings."}))
    coach.run_coach(job["id"], tmp_path / "v.mp4", None, "show my best rallies and fix my forehand")
    done = jobs.load(job["id"])
    assert calls == ["detect_rallies", "cut_highlights", "extract_pose", "render_breakdown"]
    assert done["status"] == "done" and done["engine"] == "fallback"
    assert "3 rallies" in done["summary"] and "Shadow 20 swings." in done["summary"]
    assert {f["name"] for f in done["agentFiles"]} >= {"/plan.md", "/rallies.json", "/pose_summary.json", "/cards.md"}


def test_tool_errors_go_back_to_the_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    job = jobs.create("coach", {})
    t = tools.make_tools(tools.Session(job["id"], url="https://youtu.be/g3n9jVP0fMU"))
    assert t["extract_pose"].invoke({}).startswith("ERROR: No video loaded yet. Call download_url")
    assert set(t) == {"download_url", "detect_rallies", "cut_highlights", "extract_pose", "render_breakdown", "match_players"}


def test_agent_failure_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "set")
    job = jobs.create("coach", {})

    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(coach, "run_agent", boom)
    monkeypatch.setitem(tools.TOOLS, "detect_rallies", lambda s, **k: {"count": 1, "rallies": [{"shots": 3}]})
    monkeypatch.setitem(tools.TOOLS, "cut_highlights", lambda s, **k: {"rallies": [1], "length_s": 9.0})
    coach.run_coach(job["id"], tmp_path / "v.mp4", None, "cut my best rallies")
    done = jobs.load(job["id"])
    assert done["status"] == "done" and done["engine"] == "fallback"
    assert "model unavailable" in done["agentError"] and done["summary"].startswith("I found 1 rally and cut it")


def test_coach_rallies_use_non_play_filter(tmp_path, monkeypatch):
    from agent import tools
    from app.rally import Rally
    from types import SimpleNamespace
    video = tmp_path / 'video.mp4'
    candidate = Rally(1, 3, 5)
    session = SimpleNamespace(need_video=lambda: video, dir=tmp_path, update=lambda **kw: None)
    monkeypatch.setattr(tools, 'find_rallies', lambda *args: [candidate])
    monkeypatch.setattr('app.floor_bounce.drop_non_play', lambda path, rs: ([], rs))
    assert tools.detect_rallies(session)['count'] == 0
    assert session.rallies == []


def test_unspecified_coaching_request_does_not_force_forehand():
    from agent.coach import plan_from_request
    assert plan_from_request('Improve my technique', False)[1] == 'auto'
    assert plan_from_request('Improve my backhand', False)[1] == 'backhand'

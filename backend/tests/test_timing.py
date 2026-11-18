"""Stage timings and Claude spend per job (timing.py)."""
from __future__ import annotations

import threading
import time
import uuid

import timing


def test_nothing_is_recorded_without_a_timer():
    import contextvars
    ctx = contextvars.Context()   # a fresh context: no job timer
    ctx.run(lambda: timing.stage("x").__enter__())
    assert ctx.run(timing.current) is None


def test_nested_stages_and_llm_calls_are_recorded_with_cost():
    t = timing.start()
    with timing.stage("tool:extract_pose"):
        with timing.stage("pose"):
            time.sleep(0.01)
        timing.llm("analyzer", "claude-opus-5-5", 2.0, input=1000, output=500, cache_write=100, cache_read=2000)
    s = t.summary()
    names = [r["stage"] for r in s["rows"]]
    assert "tool:extract_pose / pose" in names and "tool:extract_pose / analyzer" in names
    llm = next(r for r in s["rows"] if r["kind"] == "llm")
    # $4/$20/$5/$0.20 per million: 0.004 + 0.010 + 0.0005 + 0.0004
    assert abs(llm["cost"] - 0.0149) < 1e-9 and s["cost_usd"] == 0.0149 and s["llm_calls"] == 1
    assert timing.cost("some-other-model", 10, 10) is None


def test_the_langchain_callback_counts_ttl_cache_writes():
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, LLMResult

    t = timing.start()
    cb = timing.callback()
    run = uuid.uuid4()
    cb.on_chat_model_start({}, [[]], run_id=run, metadata={"lc_agent_name": "coach_writer"})
    # LangChain's shape: input_tokens includes cached tokens; TTL writes replace cache_creation.
    msg = AIMessage(content="x", response_metadata={"model_name": "claude-sonnet-5-5"},
                    usage_metadata={"input_tokens": 1600, "output_tokens": 50, "total_tokens": 1650,
                                    "input_token_details": {"cache_read": 1000, "cache_creation": 0,
                                                            "ephemeral_5m_input_tokens": 500}})
    threading.Thread(target=cb.on_llm_end, args=(LLMResult(generations=[[ChatGeneration(message=msg)]]),),
                     kwargs={"run_id": run}).start()
    time.sleep(0.2)
    row = t.summary()["rows"][0]
    assert row["stage"] == "llm:coach_writer" and (row["input"], row["cache_write"], row["cache_read"]) == (100, 500, 1000)

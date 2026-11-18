"""Where a job's time and Claude spend go: named stages and every LLM call, per job.

A pipeline wraps its steps in `stage("name")`; LLM calls are recorded with `llm(...)`
(the Claude analyzer) or the LangChain callback `callback()` (the deep agent). Nothing is
recorded unless a job started a timer with `start()`, so library code can call these freely.
The rows go to the job record as `timings` (see `Timer.summary`)."""
from __future__ import annotations

import contextvars
import threading
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator

# $ per million tokens: input, output, cache write (5-minute TTL, 1.25x), cache read.
# Anthropic list prices as of 2026-11 (claude-api skill, models table and prompt-caching economics).
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
}

_timer: contextvars.ContextVar["Timer | None"] = contextvars.ContextVar("timer", default=None)
_path: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar("stage_path", default=())


def cost(model: str, input: int = 0, output: int = 0, cache_write: int = 0, cache_read: int = 0) -> float | None:
    """Dollars for one call, or None for a model without a price here."""
    price = next((p for name, p in PRICES.items() if model and model.startswith(name)), None)
    if price is None:
        return None
    return (input * price[0] + output * price[1] + cache_write * price[2] + cache_read * price[3]) / 1e6


class Timer:
    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.rows: list[dict] = []
        self._lock = threading.Lock()

    def add(self, row: dict) -> None:
        with self._lock:
            self.rows.append(row)

    def summary(self) -> dict:
        """Totals for the job record: wall time, LLM calls, tokens and dollars."""
        llm = [r for r in self.rows if r.get("kind") == "llm"]
        dollars = [r["cost"] for r in llm if r.get("cost") is not None]
        return {
            "wall_s": round(time.monotonic() - self.t0, 1),
            "llm_calls": len(llm),
            "llm_s": round(sum(r["seconds"] for r in llm), 1),
            "tokens": {k: sum(r.get(k, 0) for r in llm) for k in ("input", "output", "cache_write", "cache_read")},
            "cost_usd": round(sum(dollars), 4) if dollars else 0.0,
            "rows": self.rows,
        }


def start() -> Timer:
    """Start timing this job (in this thread and the threads it hands work to)."""
    t = Timer()
    _timer.set(t)
    _path.set(())
    return t


def current() -> Timer | None:
    return _timer.get()


@contextmanager
def stage(name: str, **info: Any) -> Iterator[None]:
    """Time a step. Nested stages are recorded with their parents' names ("tool:x / pose")."""
    t = _timer.get()
    if t is None:
        yield
        return
    path = _path.get() + (name,)
    token = _path.set(path)
    begin = time.monotonic()
    try:
        yield
    finally:
        _path.reset(token)
        end = time.monotonic()
        t.add({"kind": "stage", "stage": " / ".join(path), "depth": len(path) - 1,
               "start_s": round(begin - t.t0, 2), "seconds": round(end - begin, 2), **info})


def timed(name: str) -> Callable:
    """Decorator form of stage()."""
    def wrap(fn: Callable) -> Callable:
        @wraps(fn)
        def inner(*args, **kwargs):
            with stage(name):
                return fn(*args, **kwargs)
        return inner
    return wrap


def llm(name: str, model: str, seconds: float, begin: float | None = None, input: int = 0, output: int = 0,
        cache_write: int = 0, cache_read: int = 0) -> None:
    """Record one Claude call. `input` excludes cached tokens (as Anthropic's usage reports it)."""
    t = _timer.get()
    if t is None:
        return
    path = _path.get()
    t.add({"kind": "llm", "stage": " / ".join(path + (name,)), "depth": len(path), "model": model,
           "start_s": round((begin if begin is not None else time.monotonic() - seconds) - t.t0, 2),
           "seconds": round(seconds, 2), "input": input, "output": output, "cache_write": cache_write,
           "cache_read": cache_read, "cost": cost(model, input, output, cache_write, cache_read)})


def record_anthropic(name: str, msg: Any, begin: float) -> None:
    """llm() from an Anthropic SDK response."""
    u = getattr(msg, "usage", None)
    llm(name, getattr(msg, "model", "") or "", time.monotonic() - begin, begin,
        input=getattr(u, "input_tokens", 0) or 0, output=getattr(u, "output_tokens", 0) or 0,
        cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
        cache_read=getattr(u, "cache_read_input_tokens", 0) or 0)


def callback():
    """A LangChain callback that records every chat-model call of the deep agent (and its
    subagents) with the agent's name, duration, tokens and cost."""
    from langchain_core.callbacks import BaseCallbackHandler

    timer = _timer.get()

    class LLMTimer(BaseCallbackHandler):
        def __init__(self) -> None:
            self.started: dict = {}

        def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kw):
            md = metadata or {}
            self.started[run_id] = (time.monotonic(), md.get("lc_agent_name") or md.get("langgraph_node") or "agent")

        def on_llm_end(self, response, *, run_id, **kw):
            begin, who = self.started.pop(run_id, (time.monotonic(), "agent"))
            try:
                msg = response.generations[0][0].message
            except (IndexError, AttributeError):
                return
            usage = getattr(msg, "usage_metadata", None) or {}
            details = usage.get("input_token_details") or {}
            read = details.get("cache_read") or 0
            # With TTL details LangChain zeroes cache_creation and reports the 5m/1h keys instead.
            write = (details.get("cache_creation") or 0) + (details.get("ephemeral_5m_input_tokens") or 0) \
                + (details.get("ephemeral_1h_input_tokens") or 0)
            model = (getattr(msg, "response_metadata", None) or {}).get("model_name") or ""
            token = _timer.set(timer)   # callbacks may run on another thread
            try:
                # LangChain's input_tokens includes the cached tokens; Anthropic's doesn't.
                llm(f"llm:{who}", model, time.monotonic() - begin, begin,
                    input=max(0, (usage.get("input_tokens") or 0) - read - write),
                    output=usage.get("output_tokens") or 0, cache_write=write, cache_read=read)
            finally:
                _timer.reset(token)

    return LLMTimer()

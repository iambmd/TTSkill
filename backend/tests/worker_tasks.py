"""Task functions for the worker tests: importable by the worker's spawned job processes."""
from __future__ import annotations

import os
import time

from app import jobs


def finish(job_id: str, note: str) -> None:
    jobs.update(job_id, status="done", progress=1.0, message=note, pid=os.getpid())


def sleep_forever(job_id: str) -> None:
    jobs.update(job_id, status="running")
    time.sleep(60)


def crash(job_id: str) -> None:
    jobs.update(job_id, status="running")
    os._exit(9)   # like an out-of-memory kill: no exception, no final status

"""Input limits shared with the frontend: one JSON file at shared/limits.json, read by both."""
from __future__ import annotations

import json
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "shared" / "limits.json"
LIMITS: dict = json.loads(FILE.read_text())

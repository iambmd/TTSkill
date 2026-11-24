"""The coaching notes a Coach job shows its user, in one stable field (`job["coaching"]`).

Markdown that always carries the biggest fix and a drill, in the same shape from every engine
(the fixed pipeline with Claude or the offline cards, the deep agent, the old fixed plan). The
page shows this; the agent's working files (`agentFiles`: /facts.json, /rallies.json...) are
internal and only shown in development."""
from __future__ import annotations

import re
from typing import Optional

import i18n

# The coaching call lists the fixes most important first, as "1. ...", "2. ...".
_FIRST = re.compile(r"^\s*1[.)]\s+(.+?)\s*$", re.M)
# A labelled drill: "**Drill:** ...", "Drill: ..." or "Bài tập: ..." (not just the word in a sentence).
_DRILL = re.compile(r"(?:\bdrill|bài tập)\s*\**\s*:\s*\**\s*(.+?)\s*$", re.I | re.M)


def first_fix(markdown: str) -> str:
    m = _FIRST.search(markdown)
    return m.group(1) if m else ""


def build(markdown: str, fix: str = "", drill: str = "", lang: str = "en") -> Optional[dict]:
    """{markdown, fix, drill}, or None when there is nothing to show. A fix or drill the text
    doesn't already hold is added as its own labelled line (in `lang`), so neither can go missing."""
    md = (markdown or "").strip()
    if not md:
        return None
    fix, drill = (fix or "").strip(), (drill or "").strip()
    extra = []
    if fix and not first_fix(md) and fix not in md:
        extra.append(f"**{i18n.t(lang, 'notes.fix')}:** {fix}")
    if drill and not _DRILL.search(md) and drill not in md:
        extra.append(f"**{i18n.t(lang, 'notes.drill')}:** {drill}")
    md = "\n\n".join([md, *extra])
    found = _DRILL.search(md)
    return {"markdown": md, "fix": first_fix(md) or fix, "drill": drill or (found.group(1) if found else "")}

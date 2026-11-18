"""The coaching notes a Coach job shows (agent/notes.py): Markdown that always has the
biggest fix and a drill, whatever wrote it."""
from __future__ import annotations

from agent import notes

# The coaching call's summary on coaching-demo (backend/eval/coach_speed/phase1-final-*).
CLAUDE = """Your legs are too straight on the forehand, so your arm does the work instead of your body.

**What I made:** A highlight reel of your top 5 rallies by shot count.

**What to work on first:**
1. **Bend your knees more.** At contact your knee angle is 157°. Ma Long's forehand is 126°.
2. **Keep your stance steady.** Hold it at about 1.8 to 2 shoulder widths.

**Keep:** Your finish is long and extended across your body.

**Drill:** Shadow-swing 20 forehands in front of a mirror."""


def test_the_coaching_calls_summary_is_kept_as_it_is():
    got = notes.build(CLAUDE, drill="Do 20 slow shadow forehands.")
    assert got["markdown"] == CLAUDE   # it already has numbered fixes and a drill: nothing added
    assert got["fix"] == "**Bend your knees more.** At contact your knee angle is 157°. Ma Long's forehand is 126°."
    assert got["drill"] == "Do 20 slow shadow forehands."


def test_a_missing_fix_or_drill_is_added_as_its_own_line():
    got = notes.build("You stand too tall. A drill helps.", fix="Sit lower.", drill="Shadow 20 swings.")
    # "a drill" in a sentence isn't a drill: only a labelled one counts
    assert got["markdown"] == "You stand too tall. A drill helps.\n\n**Biggest fix:** Sit lower.\n\n**Drill:** Shadow 20 swings."
    assert got["fix"] == "Sit lower." and got["drill"] == "Shadow 20 swings."


def test_the_old_fixed_plans_one_paragraph_keeps_its_fix_and_drill():
    text = "I found 3 rallies. Work on: Load low, lift through, end high. Drill: Shadow 20 swings."
    got = notes.build(text, fix="Load low, lift through, end high.", drill="Shadow 20 swings.")
    assert got == {"markdown": text, "fix": "Load low, lift through, end high.", "drill": "Shadow 20 swings."}
    assert notes.build("Drill: shadow swings")["drill"] == "shadow swings"


def test_nothing_to_show_is_none():
    assert notes.build("") is None and notes.build("   \n") is None and notes.build(None) is None

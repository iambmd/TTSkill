"""Analysis errors that carry advice suitable for the player."""
from __future__ import annotations

from messages import Keyed


class NoPlayer(Keyed):
    """Too few frames show a player to measure their stroke. Built from a Msg (messages.py), so
    the page shows it in the reader's language."""

"""Analysis errors that carry advice suitable for the player."""
from __future__ import annotations


class NoPlayer(ValueError):
    """Too few frames show a player to measure their stroke."""

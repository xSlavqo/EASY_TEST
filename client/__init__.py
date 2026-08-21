"""Klient gry — start, zamknięcie, fokus okna."""

from .game_launcher import close_windows, run_game
from .window import activate_window

__all__ = [
    "activate_window",
    "close_windows",
    "run_game",
]

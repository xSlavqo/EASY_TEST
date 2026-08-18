"""Klient gry — start, zamknięcie, fokus okna."""

from .game_launcher import close_windows, run_game, start_game, start_launcher
from .window import activate_window, game_window_rect

__all__ = [
    "activate_window",
    "close_windows",
    "game_window_rect",
    "run_game",
    "start_game",
    "start_launcher",
]

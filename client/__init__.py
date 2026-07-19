"""Klient gry — start, zamknięcie, fokus okna."""

from .game_launcher import (
    activate_window,
    close_windows,
    run_game,
    start_game,
    start_launcher,
)

__all__ = [
    "activate_window",
    "close_windows",
    "run_game",
    "start_game",
    "start_launcher",
]

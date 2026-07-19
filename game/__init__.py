"""Automatyzacja UI w grze — widoki, nawigacja, bohaterowie."""

from .navigation import go_to_setting
from .view_detector import (
    GameView,
    detect_view,
    go_on_map,
    go_to_city,
    in_game,
    run_test,
    switch_view,
)

__all__ = [
    "GameView",
    "detect_view",
    "go_on_map",
    "go_to_city",
    "go_to_setting",
    "in_game",
    "run_test",
    "switch_view",
]

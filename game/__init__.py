"""Automatyzacja UI w grze — widoki, nawigacja, bohaterowie."""

from .navigation import go_to_alliance_menu, go_to_setting
from .view_detector import (
    go_to_city,
    go_to_map,
    in_game,
    is_in_game,
)

__all__ = [
    "go_to_alliance_menu",
    "go_to_city",
    "go_to_map",
    "go_to_setting",
    "in_game",
    "is_in_game",
]

"""Nawigacja po UI gry — ustawienia, sojusz."""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import find_and_click, find_on_screen, press_key
from log import logger
from state.stop import sleep as stop_sleep

from .view_detector import in_game

_NAV_DIR = _ROOT / "templates" / "navigation"
_ALLIANCE_DIR = _ROOT / "templates" / "aliance"
_SETTING_BUTTON = _NAV_DIR / "setting_button.png"
_COLLECT_ALLY_RSS = _ALLIANCE_DIR / "collect_ally_rss.png"
_ALLY_TERRITORY_MENU = _ALLIANCE_DIR / "ally_territory_menu.png"

_SEARCH_TIMEOUT = 3.0
_MAX_ATTEMPTS = 8
_ESC_SETTLE_DELAY = (0.3, 0.6)
_AFTER_CLICK_DELAY = (0.4, 0.9)
_ALLY_MENU_CHECK_TIMEOUT = 2.0


def go_to_alliance_menu() -> bool:
    """
    Otwórz menu sojuszu (O). True = UI sojuszu widoczne.

    False = po O nie ma ally_territory_menu — coś poszło nie tak.
    """
    if find_on_screen(_COLLECT_ALLY_RSS, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        return True
    if find_on_screen(_ALLY_TERRITORY_MENU, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        return True

    if not in_game():
        logger.error("nie jesteśmy w grze — nie można otworzyć menu sojuszu")
        return False

    press_key("o")

    if not find_on_screen(_ALLY_TERRITORY_MENU, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        logger.error("po O brak ally_territory_menu — nie udało się otworzyć sojuszu")
        return False

    return True


def go_to_setting() -> bool:
    """
    Przejdź do ustawień — ESC, szukaj setting_button.png (3 s), powtórz max 8×.

    Zwraca True, gdy przycisk został znaleziony i kliknięty.
    """
    for _ in range(_MAX_ATTEMPTS):
        press_key("esc")
        stop_sleep(random.uniform(*_ESC_SETTLE_DELAY))

        if find_and_click(_SETTING_BUTTON, timeout=_SEARCH_TIMEOUT):
            stop_sleep(random.uniform(*_AFTER_CLICK_DELAY))
            return True

    logger.error(
        "nie udało się przejść do ustawień — brak setting_button.png po %s próbach",
        _MAX_ATTEMPTS,
    )
    return False

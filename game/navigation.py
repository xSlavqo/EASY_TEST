"""Nawigacja po UI gry — ustawienia, sojusz."""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import activate_window
from input import find_and_click, find_on_screen, press_key
from log import logger
from state.stop import sleep as stop_sleep

from .view_detector import in_game

_NAV_DIR = _ROOT / "templates" / "navigation"
_ALLIANCE_DIR = _ROOT / "templates" / "alliance"
_SETTING_BUTTON = _NAV_DIR / "setting_button.png"
_COLLECT_ALLY_RSS = _ALLIANCE_DIR / "collect_ally_rss.png"
_ALLY_TERRITORY_MENU = _ALLIANCE_DIR / "ally_territory_menu.png"
_NOT_IN_ALLIANCE = _ALLIANCE_DIR / "not_in_alliance.png"

_SEARCH_TIMEOUT = 3.0
_MAX_ATTEMPTS = 8
_ESC_SETTLE_DELAY = (0.3, 0.6)
_AFTER_CLICK_DELAY = (0.4, 0.9)
_ALLY_MENU_CHECK_TIMEOUT = 2.0


def go_to_alliance_menu() -> bool:
    """
    Otwórz menu sojuszu (O). True = terytorium albo awaryjny ekran DOŁĄCZ.

    DOŁĄCZ = OCR sojuszu się pomylił; wyłączamy taski ally u tego hero.
    False = po O nie ma ani terytorium, ani DOŁĄCZ.
    """
    if find_on_screen(_COLLECT_ALLY_RSS, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        return True
    if find_on_screen(_ALLY_TERRITORY_MENU, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        return True

    if not in_game():
        logger.error("nie jesteśmy w grze — nie można otworzyć menu sojuszu")
        return False

    activate_window("game")
    press_key("o")

    if find_on_screen(_ALLY_TERRITORY_MENU, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        return True

    if find_on_screen(_NOT_IN_ALLIANCE, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        from game.hero_manager import manager

        logger.warning("DOŁĄCZ (not_in_alliance) — wyłącznik awaryjny tasków sojuszu")
        manager.mark_not_in_alliance()
        return True

    logger.error("po O brak ally_territory_menu i not_in_alliance — nie udało się otworzyć sojuszu")
    return False


def go_to_setting() -> bool:
    """
    Przejdź do ustawień — szukaj setting_button.png (3 s);
    jak brak, ESC i powtórz (max 8×).
    """
    activate_window("game")
    for _ in range(_MAX_ATTEMPTS):
        if find_and_click(_SETTING_BUTTON, timeout=_SEARCH_TIMEOUT):
            stop_sleep(random.uniform(*_AFTER_CLICK_DELAY))
            return True
        press_key("esc")
        stop_sleep(random.uniform(*_ESC_SETTLE_DELAY))

    logger.error(
        "nie udało się przejść do ustawień — brak setting_button.png po %s próbach",
        _MAX_ATTEMPTS,
    )
    return False

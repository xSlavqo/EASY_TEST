"""
Zadanie: gather_buff — wykrywanie i aktywacja buffa zbierania.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game import in_game
from input import (
    click_region,
    find_and_click,
    find_on_screen,
    press_key,
    wait_for_any_on_screen,
)
from log import logger
from state.stop import sleep as stop_sleep

_BUFF_DIR = _ROOT / "templates" / "gather_buff"
_ACTIVE_DIR = _BUFF_DIR / "active"
_ACTIVATE_DIR = _BUFF_DIR / "activate"

# Ikony aktywnego buffa na pasku (8h / 24h).
_BUFF_ACTIVE_8H = _ACTIVE_DIR / "buff_active_8h.png"
_BUFF_ACTIVE_24H = _ACTIVE_DIR / "buff_active_24h.png"
_ACTIVE_BUFF_TEMPLATES = (_BUFF_ACTIVE_8H, _BUFF_ACTIVE_24H)

# Ekwipunek → zakładka buffów → wybór buffa → użyj → opcjonalnie TAK.
_BUFF_ITEM_24H = _ACTIVATE_DIR / "buff_item_24h.png"
_BUFF_ITEM_8H = _ACTIVATE_DIR / "buff_item_8h.png"
_BUFF_ITEM_TEMPLATES = (_BUFF_ITEM_24H, _BUFF_ITEM_8H)
_BUFF_USE_BUTTON = _ACTIVATE_DIR / "buff_use_button.png"
_BUFF_CONFIRM_YES = _ACTIVATE_DIR / "buff_confirm_yes.png"

_SETTING_BUTTON = _ROOT / "templates" / "navigation" / "setting_button.png"

_BUFFS_TAB_REGION = (293, 596, 67, 59)
_ACTION_DELAY = (0.5, 1.0)
_ACTIVE_BUFF_TIMEOUT = 2.0
_CLICK_TIMEOUT = 7.0
_CONFIRM_TIMEOUT = 3.0


def gather_buff() -> bool:
    """True = OK / skip. False = błąd UI (manager wyłącza task u hero)."""
    if not in_game():
        logger.error("gather_buff — nie w grze (miasto/mapa)")
        return False

    if find_on_screen(_SETTING_BUTTON, timeout=0.0):
        press_key("esc")
        stop_sleep(random.uniform(1.5, 2.5))

    if _is_buff_active():
        return True

    return _activate_buff()


def _is_buff_active() -> bool:
    """True = wykryto aktywny buff (8h albo 24h). False = brak na ekranie."""
    found = wait_for_any_on_screen(
        list(_ACTIVE_BUFF_TEMPLATES),
        threshold=0.98,
        timeout=_ACTIVE_BUFF_TIMEOUT,
    )
    return found is not None


def _activate_buff() -> bool:
    """Otwórz ekwipunek, wybierz buff (24h → 8h) i aktywuj."""
    press_key("i")
    stop_sleep(random.uniform(*_ACTION_DELAY))

    click_region(*_BUFFS_TAB_REGION)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    found = wait_for_any_on_screen(list(_BUFF_ITEM_TEMPLATES), timeout=_CLICK_TIMEOUT)
    if found is None:
        logger.error("gather_buff — nie znaleziono buff_item_24h / buff_item_8h")
        return False

    _, item_rect = found
    click_region(*item_rect)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_BUFF_USE_BUTTON, timeout=_CLICK_TIMEOUT):
        logger.error("gather_buff — nie znaleziono buff_use_button")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    find_and_click(_BUFF_CONFIRM_YES, timeout=_CONFIRM_TIMEOUT)
    stop_sleep(random.uniform(*_ACTION_DELAY))
    return True

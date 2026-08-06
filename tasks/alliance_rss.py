"""
Zadanie: alliance RSS.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game import go_to_alliance_menu
from input import find_and_click, press_key
from log import logger
from state.stop import sleep as stop_sleep

_ALLIANCE_DIR = _ROOT / "templates" / "aliance"
_ALLY_TERRITORY_MENU = _ALLIANCE_DIR / "ally_territory_menu.png"
_COLLECT_ALLY_RSS = _ALLIANCE_DIR / "collect_ally_rss.png"

_CLICK_TIMEOUT = 30.0
_ACTION_DELAY = (0.5, 1.0)
_AFTER_COLLECT_DELAY = (2.0, 3.0)


def alliance_rss() -> bool:
    if not go_to_alliance_menu():
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_ALLY_TERRITORY_MENU, timeout=_CLICK_TIMEOUT):
        logger.error("nie znaleziono ally_territory_menu.png")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_COLLECT_ALLY_RSS, timeout=_CLICK_TIMEOUT):
        logger.error("nie znaleziono collect_ally_rss.png")
        return False
    stop_sleep(random.uniform(*_AFTER_COLLECT_DELAY))

    return True

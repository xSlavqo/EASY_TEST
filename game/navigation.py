"""Nawigacja po UI gry — ustawienia."""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import find_and_click, press_key
from log import logger

_NAV_DIR = _ROOT / "templates" / "navigation"
_SETTING_BUTTON = _NAV_DIR / "setting_button.png"

_SEARCH_TIMEOUT = 3.0
_MAX_ATTEMPTS = 8
_ESC_SETTLE_DELAY = (0.3, 0.6)
_AFTER_CLICK_DELAY = (0.4, 0.9)


def _pause(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def go_to_setting() -> bool:
    """
    Przejdź do ustawień — ESC, szukaj setting_button.png (3 s), powtórz max 8×.

    Zwraca True, gdy przycisk został znaleziony i kliknięty.
    """
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        press_key("esc")
        _pause(*_ESC_SETTLE_DELAY)

        if find_and_click(_SETTING_BUTTON, timeout=_SEARCH_TIMEOUT):
            _pause(*_AFTER_CLICK_DELAY)
            return True

        if attempt < _MAX_ATTEMPTS:
            logger.warning(
                "setting_button.png niewidoczny — ponawiam (próba %s/%s)",
                attempt,
                _MAX_ATTEMPTS,
            )

    logger.error(
        "nie udało się przejść do ustawień — brak setting_button.png po %s próbach",
        _MAX_ATTEMPTS,
    )
    return False

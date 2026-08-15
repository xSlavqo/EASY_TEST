"""
Zamykanie znanych popupów blokujących UI gry.

Wołane z detect_view, gdy brak miasta/mapy.
Nowy popup: PNG do templates/popups/ + jedna linia w _POPUPS.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import find_and_click
from log import logger
from state.stop import check_stop, sleep as stop_sleep

_POPUPS_DIR = _ROOT / "templates" / "popups"

# (ścieżka do PNG przycisku zamknięcia, krótka nazwa do logów)
# Szablon = to, w co klikamy (np. czerwone X).
_POPUPS: tuple[tuple[Path, str], ...] = (
    (_POPUPS_DIR / "popup1.png", "popup1"),
)

_SEARCH_TIMEOUT = 1.5
_AFTER_CLOSE_DELAY = (0.5, 1.0)
# Po zamknięciu jednego może od razu wyskoczyć kolejny — zamykamy w pętli.
_MAX_CLOSES = 5


def dismiss_popups(
    *,
    timeout: float = _SEARCH_TIMEOUT,
    max_closes: int = _MAX_CLOSES,
) -> bool:
    """
    Szukaj znanych przycisków zamknięcia i klikaj, aż znikną albo limit.

    Po każdym zamknięciu krótka pauza i kolejne szukanie — dzięki temu
    „zamknąłem A → wyskoczyło B” łapie się w tym samym wywołaniu.

    True = zamknięto co najmniej jeden popup.
    False = nic nie znaleziono (to nie błąd — po prostu czysty ekran).
    """
    closed_any = False

    for _ in range(max_closes):
        check_stop()
        if not _close_one(timeout=timeout):
            break
        closed_any = True
        stop_sleep(random.uniform(*_AFTER_CLOSE_DELAY))

    return closed_any


def _close_one(*, timeout: float) -> bool:
    """Kliknij pierwszy znaleziony przycisk z _POPUPS. True = kliknięto."""
    for template, name in _POPUPS:
        if not template.is_file():
            logger.warning("popups — brak pliku szablonu: %s", template)
            continue
        if find_and_click(template, timeout=timeout):
            logger.info("popups — zamknięto %s", name)
            return True
    return False

"""
Zamykanie znanych popupów blokujących UI gry.

Wołane przy braku dopasowania szablonu (image.py) oraz z in_game / is_in_game.
Nowy popup: PNG do templates/popups/ + jedna linia w _POPUPS.

Klik przez locate_template + click_region — NIE przez find_and_click.
Inaczej: find_and_click → popup → find_and_click → pętla w kółko.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import click_region, locate_template
from log import logger
from state.stop import check_stop, sleep as stop_sleep

_POPUPS_DIR = _ROOT / "templates" / "popups"

# (ścieżka do PNG przycisku zamknięcia, krótka nazwa do logów)
# Szablon = to, w co klikamy (np. czerwone X).
_POPUPS: tuple[tuple[Path, str], ...] = (
    (_POPUPS_DIR / "popup1.png", "popup1"),
    (_POPUPS_DIR / "popup2.png", "popup2"),
)

_MATCH_THRESHOLD = 0.99
_AFTER_CLOSE_DELAY = (0.5, 1.0)
# Po zamknięciu jednego może od razu wyskoczyć kolejny — zamykamy w pętli.
_MAX_CLOSES = 5


def dismiss_popups(
    *,
    timeout: float = 0.0,
    max_closes: int = _MAX_CLOSES,
) -> bool:
    """
    Szukaj znanych przycisków zamknięcia i klikaj, aż znikną albo limit.

    Jedno sprawdzenie = jeden zrzut na szablon (bez czekania).
    timeout zostaje w API przez stare wywołania — nie czeka na pojawienie się X.

    True = zamknięto co najmniej jeden popup.
    False = nic nie znaleziono (to nie błąd — po prostu czysty ekran).
    """
    _ = timeout
    closed_any = False

    for _ in range(max_closes):
        check_stop()
        if not _close_one():
            break
        closed_any = True
        stop_sleep(random.uniform(*_AFTER_CLOSE_DELAY))

    return closed_any


def _close_one() -> bool:
    """Kliknij pierwszy znaleziony przycisk z _POPUPS. True = kliknięto."""
    for template, name in _POPUPS:
        if not template.is_file():
            logger.warning("popups — brak pliku szablonu: %s", template)
            continue
        rect = locate_template(template, _MATCH_THRESHOLD)
        if rect is not None:
            click_region(*rect)
            logger.info("popups — zamknięto %s", name)
            return True
    return False

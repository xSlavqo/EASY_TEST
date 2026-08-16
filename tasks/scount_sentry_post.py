"""
Zadanie: scount_sentry_post — wejście w SSP i zużywanie prób scouta.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game import go_to_city
from game.hero_manager import manager
from input import (
    click_region,
    find_and_click,
    find_on_screen,
    press_key,
    wait_for_any_on_screen,
)
from log import logger
from state.stop import check_stop, sleep as stop_sleep

# in_ssp: 0.99 bywa za ostre (noc / lekko inny UI) — enter schodzi niżej,
# więc potwierdzenie też musi być łagodniejsze niż domyślne 0.99.
_IN_SSP_THRESHOLD = 0.98
_IN_SSP_TIMEOUT = 7.0


def scount_sentry_post() -> bool:
    """Wejdź w SSP i zużywaj próby (try1/try2), aż znikną. True = OK."""
    if not _ssp_entry():
        # Soft-skip: budynek/wejście niedostępne — nie failuj cyklu.
        logger.warning("scount_sentry_post — nie udało się wejść do SSP")
        return True

    ssp_dir = _ROOT / "templates" / "ssp"
    # ssp_try1 = „Szybka pomoc”, ssp_try2 = „Odbierz wszystko”.
    try_buttons = [ssp_dir / "ssp_try1.png", ssp_dir / "ssp_try2.png"]

    while True:
        check_stop()

        use_hit = wait_for_any_on_screen(try_buttons, timeout=5.0)
        if use_hit is not None:
            _, use_btn_rect = use_hit
            click_region(*use_btn_rect)
            stop_sleep(random.uniform(0.5, 1.5))
            press_key("esc")
            stop_sleep(random.uniform(2.0, 3.5))
            continue

        # Brak przycisków — może popup sklepu; zamknij i spróbuj jeszcze raz.
        if _ssp_popup_close():
            continue

        # Brak try1/try2 i brak popupu → koniec (próby wyczerpane / panel pusty).
        return True


def _ssp_entry() -> bool:
    """
    Wejdź w Sentry Post, albo True gdy już jesteśmy w środku (in_ssp.png).

    ssp_enter: próg 1.00 → 0.88 co 0.02 (7 prób), każde szukanie max 3 s.
    Po kliknięciu musi potwierdzić in_ssp.png (próg 0.98, do 7 s); brak → error + False (soft-skip).
    """
    ssp_dir = _ROOT / "templates" / "ssp"
    in_ssp = ssp_dir / "in_ssp.png"
    sentry_enter = ssp_dir / "ssp_enter.png"

    if find_on_screen(
        in_ssp, timeout=1.5, threshold=_IN_SSP_THRESHOLD
    ):
        return True

    if not go_to_city():
        logger.error("ssp_entry — nie udało się przejść do miasta")
        return False
    stop_sleep(random.uniform(0.5, 1.0))

    # 1.00, 0.98, …, 0.88 — 7 prób, każde okno szukania 3 s.
    thresholds = [1.0 - 0.02 * i for i in range(7)]
    for threshold in thresholds:
        check_stop()
        if not find_and_click(sentry_enter, timeout=3.0, threshold=threshold):
            continue

        stop_sleep(random.uniform(3.0, 4.7))
        if find_on_screen(
            in_ssp, timeout=_IN_SSP_TIMEOUT, threshold=_IN_SSP_THRESHOLD
        ):
            return True

        # Kliknięto, ale nie weszliśmy — soft-skip + screen (error) na Discord.
        logger.error(
            "ssp_entry — brak in_ssp po kliknięciu ssp_enter "
            "(próg enter %.2f, in_ssp ≥%.2f) na %s — pomijam SSP",
            threshold,
            _IN_SSP_THRESHOLD,
            _logged_in_hero_label(),
        )
        return False

    logger.warning("ssp_entry — nie znaleziono ssp_enter.png (1.00→0.88)")
    return False


def _logged_in_hero_label() -> str:
    """email/hero_id zalogowanego bohatera, albo '?'."""
    for hero in manager.heroes:
        if hero.logged_in:
            return f"{hero.email}/{hero.id}"
    return "?"


def _ssp_popup_close() -> bool:
    """
    Gdy widać ssp_popup.png — kliknij X i wróć True.
    Brak popupu → False (to nie błąd).
    """
    shop_popup = _ROOT / "templates" / "ssp" / "ssp_popup.png"

    if not find_on_screen(shop_popup, timeout=1.5):
        return False

    # Przycisk zamknięcia popupu (coord_picker 1920×1080).
    popup_close_btn = (1514, 259, 34, 30)
    click_region(*popup_close_btn)
    stop_sleep(random.uniform(0.5, 1.0))
    return True

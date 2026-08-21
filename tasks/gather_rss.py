"""
Zadanie: zbieranie RSS (surowce) w grze.
"""

from __future__ import annotations

import random
import re
import sys
import time
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import (
    DEFAULT_THRESHOLD,
    click_region,
    find_and_click,
    get_text,
    locate_template,
    press_key,
)
from log import logger
from state.settings import settings
from state.stop import check_stop, sleep as stop_sleep

from game import go_to_map
from game.hero_manager import manager

# Ikony surowców w dolnym pasku wyszukiwania (1920×1080) — (x,y,w,h), label, key
# Włączanie: gather_rss_gold / gather_rss_wood / gather_rss_ore w data/config.json
_RESOURCES = (
    ((700, 996, 93, 32), "kopalnia złota", "gold"),
    ((881, 991, 127, 43), "obóz drwali", "wood"),
    ((1127, 991, 104, 42), "kopalnia rudy", "ore"),
)
_ACTION_DELAY = (0.3, 0.7)
_LEVEL_CLICK_DELAY = (0.05, 0.14)
_ICON_CLICK_MARGIN = 0.15
_CLICK_TIMEOUT = 30.0
_OPTIONAL_CLICK_TIMEOUT = 6.0
_FIND_RESULT_TIMEOUT = (3.0, 5.0)
_LEVEL_CLICK_TIMEOUT = 8.0
_MAX_LEGION_SENDS = 5
_MAX_SEND_RETRIES = 3
_AFTER_SEND_DELAY = (0.7, 1.2)

# OCR poziomu w popupie — napis jeździ w poziomie z suwakiem (szerokość zostaje).
# y/h z wąskiego wycinka tekstu (bez uchwytu suwaka): y=761, h=19.
_LEVEL_OCR_Y = 761
_LEVEL_OCR_H = 19
_LEVEL_OCR_REGIONS = {
    "gold": (570, _LEVEL_OCR_Y, 350, _LEVEL_OCR_H),
    "wood": (786, _LEVEL_OCR_Y, 351, _LEVEL_OCR_H),
    "ore": (1010, _LEVEL_OCR_Y, 350, _LEVEL_OCR_H),
}
_LEVEL_OCR_ALLOWLIST = "0123456789"
_RSS_LEVEL_MIN = 1
_RSS_LEVEL_MAX = 10
_LEVEL_ADJUST_MAX_CLICKS = 15

# Liczba legionów w polu zbierania — dwa regiony (UI się przemieszcza), format „aktualne/maks”.
_LEGION_COUNT_REGIONS = (
    (1865, 541, 42, 20),   # pierwszy
    (1872, 507, 36, 20),   # drugi
)
_LEGION_COUNT_ALLOWLIST = "0123456789/"

_RSS_TEMPLATES_DIR = _ROOT / "templates" / "rss"
_RSS_FIND = _RSS_TEMPLATES_DIR / "rss_find.png"
_RSS_PREPARE_TO_GATHER = _RSS_TEMPLATES_DIR / "rss_prepare_to_gather.png"
_RSS_CREATE_LEGION = _RSS_TEMPLATES_DIR / "rss_create_legion.png"
_RSS_DELETE_ONE_HERO = _RSS_TEMPLATES_DIR / "rss_delete_one_hero.png"
_LEGION_START = _RSS_TEMPLATES_DIR / "legion_start.png"
_RSS_LEVEL_PLUS = _RSS_TEMPLATES_DIR / "increase_level.png"
_RSS_LEVEL_MINUS = _RSS_TEMPLATES_DIR / "decrease_level.png"

_SendResult = Literal["sent", "sent_last", "no_more", "failed"]

_last_resource: str | None = None


def gather_rss() -> tuple[bool, int]:
    """
    Wykonaj sekwencję zbierania RSS — do _MAX_LEGION_SENDS wysłanych legionów.

    Zwraca (ok, marches_sent). ok=False → manager wyłącza task u hero.
    """

    if not go_to_map():
        logger.error("nie udało się przejść na mapę")
        return False, 0

    resource = _pick_resource()
    if resource is None:
        logger.error("brak włączonych surowców w config (gather_rss_gold/wood/ore)")
        return False, 0

    # Raz na hero: wybór surowca + ustawienie poziomu (kolejne legiony w tej sesji pomijają).
    set_rss = True

    legions_sent = 0
    for legion_idx in range(_MAX_LEGION_SENDS):
        check_stop()
        for attempt in range(1, _MAX_SEND_RETRIES + 1):
            result, set_rss = _try_send_one_legion(resource, set_rss=set_rss)

            if result in ("sent", "sent_last"):
                legions_sent += 1
                if result == "sent_last":
                    return True, legions_sent
                # UI po wysłaniu musi się odświeżyć zanim znowu F.
                stop_sleep(random.uniform(*_AFTER_SEND_DELAY))
                break

            if result == "no_more":
                return True, legions_sent

            logger.error(
                "wysyłanie legionu %s nieudane (próba %s/%s) — wracam na mapę",
                legion_idx + 1,
                attempt,
                _MAX_SEND_RETRIES,
            )
            if not go_to_map():
                logger.error("nie udało się wrócić na mapę po błędzie")
                return False, legions_sent
        else:
            logger.error(
                "nie udało się wysłać legionu %s po %s próbach",
                legion_idx + 1,
                _MAX_SEND_RETRIES,
            )
            return False, legions_sent

    return True, legions_sent


# --- pomocnicze (kolejność: jak woła gather_rss, potem jak woła _try_send_one_legion) ---


def _pick_resource():
    """Losuj włączony surowiec; pomiń _last_resource, jeśli są inne opcje."""
    global _last_resource
    enabled = {
        "gold": settings.gather_rss_gold,
        "wood": settings.gather_rss_wood,
        "ore": settings.gather_rss_ore,
    }
    candidates = [r for r in _RESOURCES if enabled.get(r[2])]
    if not candidates:
        return None
    if _last_resource is not None and len(candidates) > 1:
        candidates = [r for r in candidates if r[2] != _last_resource]
    picked = random.choice(candidates)
    _last_resource = picked[2]
    return picked


def _try_send_one_legion(
    resource,
    *,
    set_rss: bool,
) -> tuple[_SendResult, bool]:
    """Jedna próba wysłania legionu od otwarcia panelu wyszukiwania."""
    press_key("f")
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if set_rss:
        click_region(*resource[0], margin=_ICON_CLICK_MARGIN)
        stop_sleep(random.uniform(*_ACTION_DELAY))
        if not _ensure_rss_level(resource[2]):
            logger.error("nie udało się ustawić poziomu RSS")
            return "failed", set_rss
    else:
        stop_sleep(random.uniform(*_ACTION_DELAY))

    # SZUKAJ → krótko czekaj na kolejny krok. Brak złoża: ten sam surowiec,
    # poziom -1, znowu SZUKAJ (bez wychodzenia z panelu).
    for _ in range(_RSS_LEVEL_MAX):
        if not find_and_click(_RSS_FIND, timeout=_CLICK_TIMEOUT):
            logger.error("nie znaleziono rss_find.png")
            return "failed", set_rss
        stop_sleep(random.uniform(*_ACTION_DELAY))

        if find_and_click(
            _RSS_PREPARE_TO_GATHER,
            timeout=random.uniform(*_FIND_RESULT_TIMEOUT),
        ):
            break

        if not _ensure_rss_level(resource[2], delta=-1):
            logger.error("nie udało się obniżyć poziomu RSS")
            return "failed", set_rss
    else:
        logger.error("po zejściu z poziomem nadal brak rss_prepare_to_gather")
        return "failed", set_rss
    stop_sleep(random.uniform(*_ACTION_DELAY))

    remaining = _legions_remaining_in_field()
    if remaining is not None and remaining <= 0:
        return "no_more", set_rss

    if not find_and_click(_RSS_CREATE_LEGION, timeout=_CLICK_TIMEOUT):
        return "no_more", set_rss
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if remaining != 1:
        find_and_click(_RSS_DELETE_ONE_HERO, timeout=_OPTIONAL_CLICK_TIMEOUT)
        stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_LEGION_START, timeout=_CLICK_TIMEOUT):
        logger.error("nie znaleziono legion_start.png")
        return "failed", set_rss

    set_rss = False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if remaining == 1:
        return "sent_last", set_rss
    return "sent", set_rss


def _target_rss_level() -> int:
    """Poziom nodów z bieżącego hero (ustawiany w panelu WWW)."""
    hero = manager.logged_in_hero()
    if hero is None:
        logger.error("brak zalogowanego hero — domyślny poziom RSS 8")
        return 8
    return int(hero.gather_rss_level)


def _ensure_rss_level(resource_key: str, *, delta: int = 0) -> bool:
    """
    Ustaw poziom wyszukiwania RSS.

    Bez delta: cel z hero.gather_rss_level.
    Z delta: cel = aktualny OCR + delta (np. -1), bez zmiany surowca.

    OCR raz → znajdź +/- raz → kliknij region N razy → OCR potwierdza.
    """
    if _level_ocr_region(resource_key) is None:
        logger.error("brak regionu OCR poziomu dla surowca %s", resource_key)
        return False

    current = _read_rss_level(resource_key)
    if current is None:
        logger.error("OCR poziomu RSS nieudany (przed ustawieniem)")
        return False

    if delta != 0:
        target = current + delta
    else:
        target = _target_rss_level()
    target = max(_RSS_LEVEL_MIN, min(_RSS_LEVEL_MAX, target))
    if delta != 0 and target == current:
        logger.error(
            "poziom RSS już na granicy (%s), nie da się zmienić o %s",
            current,
            delta,
        )
        return False

    diff = target - current
    if diff == 0:
        return True

    template = _RSS_LEVEL_PLUS if diff > 0 else _RSS_LEVEL_MINUS
    clicks = abs(diff)
    if clicks > _LEVEL_ADJUST_MAX_CLICKS:
        logger.error(
            "różnica poziomu %s za duża (max %s klików)",
            clicks,
            _LEVEL_ADJUST_MAX_CLICKS,
        )
        return False

    button = _locate_level_button(template)
    if button is None:
        logger.error("nie znaleziono przycisku poziomu")
        return False

    for _ in range(clicks):
        check_stop()
        click_region(*button, margin=_ICON_CLICK_MARGIN)
        stop_sleep(random.uniform(*_LEVEL_CLICK_DELAY))

    confirmed = _read_rss_level(resource_key)
    if confirmed is None:
        logger.error("OCR poziomu RSS nieudany (po ustawieniu)")
        return False
    if confirmed != target:
        logger.error(
            "poziom RSS po klikach: %s, oczekiwano %s",
            confirmed,
            target,
        )
        return False

    return True


def _level_ocr_region(resource_key: str) -> tuple[int, int, int, int] | None:
    """Pełny region OCR poziomu — napis przesuwa się z suwakiem."""
    return _LEVEL_OCR_REGIONS.get(resource_key)


def _read_rss_level(resource_key: str) -> int | None:
    """OCR „Poziom X” → liczba 1..10 albo None."""
    region = _level_ocr_region(resource_key)
    if region is None:
        return None
    text = get_text(region, _LEVEL_OCR_ALLOWLIST)
    if text is None:
        return None
    return _parse_rss_level(text)


def _parse_rss_level(text: str) -> int | None:
    """
    Z surowego OCR wyciągnij poziom 1..max.

    „10” ma pierwszeństwo. Długie śmieci (np. „801”) → ostatnia cyfra 1–9,
    bo OCR często dokleja artefakty z lewej (uchwyt / „o”→0).
    """
    raw = text.strip()
    if not raw:
        return None
    if "10" in raw:
        return 10

    for chunk in re.findall(r"\d+", raw):
        value = int(chunk)
        if _RSS_LEVEL_MIN <= value <= _RSS_LEVEL_MAX:
            return value
        # „80” → 8; „801” → 1 (nie pierwsza cyfra — to bywa uchwyt suwaka)
        for ch in reversed(chunk):
            digit = int(ch)
            if _RSS_LEVEL_MIN <= digit <= 9:
                return digit
    return None


def _locate_level_button(template) -> tuple[int, int, int, int] | None:
    """Znajdź przycisk +/- raz — zwraca (x, y, w, h) albo None."""
    deadline = time.monotonic() + _LEVEL_CLICK_TIMEOUT
    while time.monotonic() < deadline:
        check_stop()
        rect = locate_template(template, DEFAULT_THRESHOLD)
        if rect is not None:
            return rect
        stop_sleep(random.uniform(0.25, 0.55))
    return None


def _legions_remaining_in_field() -> int | None:
    """
    OCR pól legionów → parsuj „2/5” → ile można jeszcze wysłać (max - current).

    None — błąd OCR; kontynuuj bez gwarancji limitu.
    0 — pole pełne.
    """
    for region in _LEGION_COUNT_REGIONS:
        text = get_text(region, _LEGION_COUNT_ALLOWLIST)
        if text is None:
            continue
        match = re.fullmatch(r"(\d)/(\d)", text.strip())
        if match is None:
            continue
        current, maximum = int(match.group(1)), int(match.group(2))
        if current > maximum:
            continue
        return maximum - current

    return None


if __name__ == "__main__":
    from state.stop import clear_stop

    clear_stop()  # jak Start w panelu WWW
    ok = _ensure_rss_level("wood")
    print("OK" if ok else "FAIL")
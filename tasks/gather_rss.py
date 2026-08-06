"""
Zadanie: zbieranie RSS (surowce) w grze.
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import click_region, find_and_click, get_text, press_key
from log import logger
from state.stop import check_stop, sleep as stop_sleep

from game import go_on_map

# Ikony surowców w dolnym pasku wyszukiwania (1920×1080) — (x,y,w,h), label, key
_RESOURCES = (
    # ((685, 981, 123, 62), "kopalnia złota", "gold"),
    # ((866, 976, 157, 73), "obóz drwali", "wood"),
    ((1112, 976, 134, 72), "kopalnia rudy", "ore"),  # kamień — tymczasowo jedyny aktywny
)
_ACTION_DELAY = (0.3, 0.7)
_ICON_CLICK_MARGIN = 0.15
_CLICK_TIMEOUT = 30.0
_OPTIONAL_CLICK_TIMEOUT = 6.0
_MAX_LEGION_SENDS = 5
_MAX_SEND_RETRIES = 3

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

_SendResult = Literal["sent", "sent_last", "no_more", "failed"]

_last_resource: str | None = None


def gather_rss() -> tuple[bool, int]:
    """
    Wykonaj sekwencję zbierania RSS — do _MAX_LEGION_SENDS wysłanych legionów.

    Zwraca (rss_done, marches_sent).
    """

    if not go_on_map():
        logger.error("nie udało się przejść na mapę")
        return False, 0

    resource = _pick_resource()
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
                break

            if result == "no_more":
                return True, legions_sent

            logger.warning(
                "wysyłanie legionu %s nieudane (próba %s/%s) — wracam na mapę",
                legion_idx + 1,
                attempt,
                _MAX_SEND_RETRIES,
            )
            if not go_on_map():
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


# --- pomocnicze ---


def _pick_resource():
    """Losuj surowiec; pomiń _last_resource, jeśli są inne opcje."""
    global _last_resource
    candidates = list(_RESOURCES)
    if _last_resource is not None and len(candidates) > 1:
        candidates = [r for r in candidates if r[2] != _last_resource]
    picked = random.choice(candidates)
    _last_resource = picked[2]
    return picked


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

    if not find_and_click(_RSS_FIND, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono rss_find.png")
        return "failed", set_rss
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_RSS_PREPARE_TO_GATHER, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono rss_prepare_to_gather.png")
        return "failed", set_rss
    stop_sleep(random.uniform(*_ACTION_DELAY))

    remaining = _legions_remaining_in_field()
    if remaining is not None and remaining <= 0:
        logger.info("wszystkie legiony po za miastem - przerywam wysyłanie")
        return "no_more", set_rss

    if not find_and_click(_RSS_CREATE_LEGION, timeout=_CLICK_TIMEOUT):
        logger.warning("brak rss_create_legion.png — koniec wysyłania legionów")
        return "no_more", set_rss
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if remaining != 1:
        if not find_and_click(_RSS_DELETE_ONE_HERO, timeout=_OPTIONAL_CLICK_TIMEOUT):
            logger.warning("brak rss_delete_one_hero.png — pomijam krok")
        stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_LEGION_START, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono legion_start.png")
        return "failed", set_rss

    set_rss = False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if remaining == 1:
        return "sent_last", set_rss
    return "sent", set_rss

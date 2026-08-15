"""
Zadanie: centrum zasobów przymierza (alliance pit).

Cykl woła task u każdego hero (due / fala). W środku: gather/building/occupied/not_built.

True  → OK u tego hero (akcja albo świadomy skip).
False → fail UI — ten hero powtarza (restart w cyklu).
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

from game import go_to_alliance_menu
from input import (
    click_region,
    find_and_click,
    find_on_screen,
    get_text,
    press_key,
    wait_for_any_on_screen,
)
from log import logger
from state.keys import ALLIANCE_PIT_STATUS, TASK_ALLIANCE_PIT
from state.schedule import schedule
from state.stop import sleep as stop_sleep
from state.store import INFO_PATH, save_data

_ALLIANCE_DIR = _ROOT / "templates" / "aliance"
_ALLY_TERRITORY_MENU = _ALLIANCE_DIR / "ally_territory_menu.png"
_COLLECT_ALLY_RSS = _ALLIANCE_DIR / "collect_ally_rss.png"
_HIDE_TAB = _ALLIANCE_DIR / "hide_tab.png"
_PIT_TAB = _ALLIANCE_DIR / "pit_tab.png"
_RSS_PIT_AVAILABLE = _ALLIANCE_DIR / "rss_pit_available.png"
_PIT_GATHER = _ALLIANCE_DIR / "pit_gather.png"
_PIT_BUILD = _ALLIANCE_DIR / "pit_build.png"
_PIT_OCCUPIED = _ALLIANCE_DIR / "pit_occupied.png"
_PIT_SEND = _ALLIANCE_DIR / "pit_send.png"
_RSS_CREATE_LEGION = _ROOT / "templates" / "rss" / "rss_create_legion.png"
_LEGION_START = _ROOT / "templates" / "rss" / "legion_start.png"

# Mały rozrzut wokół środka mapy (pit po kliknięciu plusa).
_PIT_CENTER_REGION = (940, 520, 40, 40)
# OCR panelu względem lewego-górnego rogu przycisku (BUDUJ/WYŚWIETL) — building/occupied.
# coord_picker: btn (548,715,166,57) → panel (460,457,344,346)
_OCR_PANEL_OFFSET = (-88, -258, 344, 346)  # dx, dy, w, h
# gather: timer po kliknięciu ZBIERZ (coord_picker 1920×1080).
_GATHER_TIMER_REGION = (647, 450, 149, 35)
_OCR_ALLOWLIST = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "ĄĆĘŁŃÓŚŹŻąćęłńóśźż "
    "0123456789:"
)
_TIMER_ALLOWLIST = "0123456789:"
_TIMER_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})")
_LOCK_BUFFER_SEC = 5 * 60  # gather/occupied — dokładny timer do zniknięcia pitu

_CLICK_TIMEOUT = 30.0
_ALLY_MENU_CHECK_TIMEOUT = 4
_HIDE_TAB_TIMEOUT = (1.5, 2.5)
_PIT_AVAILABLE_TIMEOUT = (2.0, 3.0)
_ACTION_DELAY = (0.5, 1.0)
_POLL_INTERVAL = (0.5, 1.5)
_MATCH_THRESHOLD = 0.99

PitStatus = Literal["gather", "building", "occupied"]
PitKind = Literal["gold_pit", "wood_pit", "ore_pit", "mana_pit"]
# Wynik wejścia w pit: jest / nie ma / nie dało się dojść UI.
PitAvailability = Literal["built", "not_built", "nav_error"]

# coord_picker 1920×1080 — konfiguracja legionu przy building (po create_legion).
_LEGION_CONFIG_REGION: tuple[int, int, int, int] = (1220, 409, 186, 19)  # 1/3 okno konfiguracji
_GATHER_REGION_BTN: tuple[int, int, int, int] = (1318, 332, 150, 45)  # 2/3 przycisk regionu zbierania
_RSS_BY_PIT_KIND: dict[PitKind, tuple[int, int, int, int]] = {
    "gold_pit": (1548, 261, 37, 38),
    "wood_pit": (1626, 262, 37, 34),
    "ore_pit": (1548, 334, 37, 34),  # stone w pickerze
    "mana_pit": (1626, 337, 35, 30),
}

_STATUS_TEMPLATES: tuple[tuple[Path, PitStatus], ...] = (
    (_PIT_GATHER, "gather"),
    (_PIT_BUILD, "building"),
    (_PIT_OCCUPIED, "occupied"),
)

_KIND_MARKERS: tuple[tuple[str, PitKind], ...] = (
    ("zlota", "gold_pit"),
    ("złota", "gold_pit"),
    ("drewna", "wood_pit"),
    ("rudy", "ore_pit"),
    ("many", "mana_pit"),
)

# Po pierwszym udanym sendzie (gather/building) kolejni hero w cyklu nadal wysyłają.
_wave_active = False
_wave_kind: PitKind | None = None
# True dopiero po udanym OCR timera/kind — fail → kolejny hero znów czyta panel.
_ocr_done = False
# not_built / occupied „koniec” — kolejni hero wołają task, ale od razu True bez UI.
_skip_rest = False


def reset_cycle_state() -> None:
    """Wyzeruj falę/OCR/skip na start cyklu (woła bot/cycle)."""
    global _wave_active, _wave_kind, _ocr_done, _skip_rest
    _wave_active = False
    _wave_kind = None
    _ocr_done = False
    _skip_rest = False


def is_wave_active() -> bool:
    """Czy trwa fala sendów — cykl: due=is_due(...) or is_wave_active()."""
    return _wave_active


def alliance_pit() -> bool:
    """
    True = OK (send / skip not_built / occupied).
    False = fail UI — cykl robi retry u tego hero.
    due sprawdza cykl; tu tylko _skip_rest / UI.
    """
    global _wave_active, _wave_kind, _ocr_done, _skip_rest

    if _skip_rest:
        return True

    # OCR tylko gdy jeszcze nie udało się odczytać timera/kind.
    read_lock = not _ocr_done

    available = _is_pit_available()
    if available == "nav_error":
        logger.warning("alliance_pit — błąd nawigacji")
        return False
    if available == "not_built":
        save_data(INFO_PATH, ALLIANCE_PIT_STATUS, "not_built")
        _wave_active = False
        _wave_kind = None
        _ocr_done = False
        _skip_rest = True
        logger.warning("pit: not_built — skip akcji u kolejnych hero")
        return True

    return _check_alliance_pit_status(read_lock=read_lock)


def _is_pit_available() -> PitAvailability:
    """
    Terytorium sojuszu → zakładka centrów → klik zielonego plusa.

    Jeśli widać collect_ally_rss (np. po alliance_rss) — pomija wejście w menu.
    built = pit jest i plus kliknięty.
    not_built = brak plusa.
    nav_error = błąd UI/nawigacji.
    """
    # Już w terytorium (np. po zbieraniu ally RSS) — nie wchodź w menu od zera.
    if not find_on_screen(_COLLECT_ALLY_RSS, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        if not go_to_alliance_menu():
            return "nav_error"
        stop_sleep(random.uniform(*_ACTION_DELAY))

        if not find_and_click(_ALLY_TERRITORY_MENU, timeout=_CLICK_TIMEOUT):
            logger.error("nie znaleziono ally_territory_menu.png")
            return "nav_error"
        stop_sleep(random.uniform(*_ACTION_DELAY))

    while find_and_click(
        _HIDE_TAB,
        timeout=random.uniform(*_HIDE_TAB_TIMEOUT),
        threshold=0.999,
    ):
        stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_PIT_TAB, timeout=_CLICK_TIMEOUT):
        logger.error("nie udało się otworzyć zakładki centrów zasobów przymierza")
        return "nav_error"
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(
        _RSS_PIT_AVAILABLE,
        timeout=random.uniform(*_PIT_AVAILABLE_TIMEOUT),
    ):
        press_key("esc")
        return "not_built"
    stop_sleep(random.uniform(5.0, 7.0))
    return "built"


def _check_alliance_pit_status(*, read_lock: bool) -> bool:
    """Klik środka → znajdź przycisk → wywołaj _if_gather / _if_building / _if_occupied."""
    click_region(*_PIT_CENTER_REGION)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    found = wait_for_any_on_screen(
        [tpl for tpl, _ in _STATUS_TEMPLATES],
        threshold=_MATCH_THRESHOLD,
        timeout=_CLICK_TIMEOUT,
        poll_interval=_POLL_INTERVAL,
    )
    if found is None:
        logger.warning("nie znaleziono pit_gather / pit_build / pit_occupied")
        return False

    index, btn_rect = found
    status = _STATUS_TEMPLATES[index][1]

    if status == "gather":
        return _if_gather(btn_rect, read_lock=read_lock)
    if status == "building":
        return _if_building(btn_rect, read_lock=read_lock)
    return _if_occupied(btn_rect, read_lock=read_lock)


def _if_gather(btn_rect: tuple[int, int, int, int], *, read_lock: bool) -> bool:
    """ZBIERZ → OCR timera → pit_send → create_legion → legion_start (fala)."""
    global _wave_active, _ocr_done

    lock_sec: float | None = None

    click_region(*btn_rect)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if read_lock:
        timer_raw = (get_text(_GATHER_TIMER_REGION, _TIMER_ALLOWLIST) or "").strip()
        match = _TIMER_RE.search(timer_raw)
        if match is None:
            logger.warning("OCR pitu — brak timera: %r", timer_raw[:120])
        else:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            lock_sec = float(h * 3600 + m * 60 + s)
            _ocr_done = True
        save_data(INFO_PATH, ALLIANCE_PIT_STATUS, "gather")

    if not find_and_click(_PIT_SEND, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono pit_send.png")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_RSS_CREATE_LEGION, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono rss_create_legion.png")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_LEGION_START, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono legion_start.png")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if lock_sec is not None:
        schedule(TASK_ALLIANCE_PIT, lock_sec + _LOCK_BUFFER_SEC)
    _wave_active = True
    return True


def _if_building(btn_rect: tuple[int, int, int, int], *, read_lock: bool) -> bool:
    """BUDUJ: OCR kind → create_legion → wybór surowca → legion_start. Bez schedule."""
    global _wave_active, _wave_kind, _ocr_done

    kind: PitKind | None = _wave_kind

    if read_lock:
        bx, by, _bw, _bh = btn_rect
        pdx, pdy, pw, ph = _OCR_PANEL_OFFSET
        panel_region = (bx + pdx, by + pdy, pw, ph)
        panel_raw = (get_text(panel_region, _OCR_ALLOWLIST) or "").strip()
        panel_lower = panel_raw.lower()

        kind = None
        for marker, pit_kind in _KIND_MARKERS:
            if marker in panel_lower:
                kind = pit_kind
                break
        if kind is None:
            logger.warning("OCR pitu — nieznany rodzaj: %r", panel_raw[:120])
        else:
            _wave_kind = kind
            _ocr_done = True

        save_data(INFO_PATH, ALLIANCE_PIT_STATUS, "building")

    click_region(*btn_rect)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_RSS_CREATE_LEGION, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono rss_create_legion.png")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    click_region(*_LEGION_CONFIG_REGION)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    click_region(*_GATHER_REGION_BTN)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if kind is not None:
        click_region(*_RSS_BY_PIT_KIND[kind])
        stop_sleep(random.uniform(*_ACTION_DELAY))
    else:
        logger.warning("building: brak kind — pomijam wybór surowca")

    if not find_and_click(_LEGION_START, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono legion_start.png")
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    _wave_active = True
    return True


def _if_occupied(btn_rect: tuple[int, int, int, int], *, read_lock: bool) -> bool:
    """Zajęty: OCR timera → schedule + skip reszty hero. Brak timera → False (retry)."""
    global _wave_active, _wave_kind, _ocr_done, _skip_rest

    if read_lock:
        bx, by, _bw, _bh = btn_rect
        pdx, pdy, pw, ph = _OCR_PANEL_OFFSET
        panel_region = (bx + pdx, by + pdy, pw, ph)
        panel_raw = (get_text(panel_region, _OCR_ALLOWLIST) or "").strip()

        match = _TIMER_RE.search(panel_raw)
        if match is None:
            logger.warning("OCR pitu — brak timera: %r", panel_raw[:120])
            return False

        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        lock_sec = float(h * 3600 + m * 60 + s)
        schedule(TASK_ALLIANCE_PIT, lock_sec + _LOCK_BUFFER_SEC)
        save_data(INFO_PATH, ALLIANCE_PIT_STATUS, "occupied")
        _ocr_done = True

    _wave_active = False
    _wave_kind = None
    _skip_rest = True
    return True


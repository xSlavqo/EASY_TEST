"""
Alliance pit — centrum zasobów sojuszu.

DWA POZIOMY STANU (nie mylić):

1) PitPhase (globalny, info.json, panel WWW)
   - not_built     — brak pitu na mapie sojuszu
   - constructing  — pit się buduje (dynamiczny czas, bez OCR timera)
   - built         — pit wybudowany, faza zbierania (OCR timera możliwy)

2) HeroView (przycisk UI u TEGO hero — szablony pit_build / pit_gather / pit_occupied)
   - can_build   (BUDUJ)     — pit w constructing, hero jeszcze nie buduje → wyślij legion
   - can_gather  (ZBIERZ)    — pit w built, hero jeszcze nie zbiera → wyślij legion
   - in_pit      (WYŚWIETL)  — pit w built, legion TEGO hero już w picie → tylko OCR

   in_pit (HeroView) NIE jest PitPhase. can_gather i in_pit = ten sam PitPhase: built.

Lista in_pit (uid/nick) = hero wysłali legion (LEGION_START lub WYŚWIETL).

TaskManager tylko woła alliance_pit() gdy włączony — reguły (sojusz, CD, lista) tu.
"""

from __future__ import annotations

import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game import go_to_alliance_menu
from game.hero_manager import manager
from game.hero_manager.hero import Hero
from input import (
    click_region,
    find_and_click,
    find_on_screen,
    get_text,
    press_key,
    wait_for_any_on_screen,
)
from log import logger
from state.keys import ALLIANCE_PIT_STATE
from state.stop import sleep as stop_sleep
from state.store import INFO_PATH, get_data, save_data

_ALLIANCE_DIR = _ROOT / "templates" / "alliance"
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
_BACK_BUTTON = _ROOT / "templates" / "navigation" / "back_button.png"

_PIT_CENTER_REGION = (940, 520, 40, 40)
_OCR_PANEL_OFFSET = (-88, -258, 344, 346)
_GATHER_TIMER_REGION = (647, 450, 149, 35)
_OCR_ALLOWLIST = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "ĄĆĘŁŃÓŚŹŻąćęłńóśźż "
    "0123456789:"
)
_TIMER_ALLOWLIST = "0123456789:"
_TIMER_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})")

_CLICK_TIMEOUT = 30.0
_ALLY_MENU_CHECK_TIMEOUT = 4
_HIDE_TAB_TIMEOUT = (1.5, 2.5)
_PIT_AVAILABLE_TIMEOUT = (2.0, 3.0)
_ACTION_DELAY = (0.5, 1.0)
_POLL_INTERVAL = (0.5, 1.5)
_MATCH_THRESHOLD = 0.99

# Faza pitu (globalna, JSON, WWW).
PitPhase = Literal["not_built", "constructing", "built"]
# Przycisk UI u bieżącego hero (nie zapisujemy jako PitPhase).
HeroView = Literal["can_gather", "can_build", "in_pit"]
PitKind = Literal["gold_pit", "wood_pit", "ore_pit", "mana_pit"]
# Wejście w mapę pitu (czy plus istnieje).
PitNavResult = Literal["pit_exists", "not_built", "nav_error", "no_alliance"]

# Stare klucze w JSON → PitPhase (migracja przy odczycie).
_LEGACY_PHASE: dict[str, PitPhase] = {
    "building": "constructing",
    "gather": "built",
    "occupied": "built",
}

_LEGION_CONFIG_REGION: tuple[int, int, int, int] = (1220, 409, 186, 19)
_GATHER_REGION_BTN: tuple[int, int, int, int] = (1318, 332, 150, 45)
_RSS_BY_PIT_KIND: dict[PitKind, tuple[int, int, int, int]] = {
    "gold_pit": (1548, 261, 37, 38),
    "wood_pit": (1626, 262, 37, 34),
    "ore_pit": (1548, 334, 37, 34),
    "mana_pit": (1626, 337, 35, 30),
}

_HERO_VIEW_TEMPLATES: tuple[tuple[Path, HeroView], ...] = (
    (_PIT_GATHER, "can_gather"),
    (_PIT_BUILD, "can_build"),
    (_PIT_OCCUPIED, "in_pit"),
)

_KIND_MARKERS: tuple[tuple[str, PitKind], ...] = (
    ("zlota", "gold_pit"),
    ("złota", "gold_pit"),
    ("drewna", "wood_pit"),
    ("rudy", "ore_pit"),
    ("many", "mana_pit"),
)
_KIND_LABELS: dict[PitKind, str] = {
    "gold_pit": "złoto",
    "wood_pit": "drewno",
    "ore_pit": "ruda",
    "mana_pit": "mana",
}

# Flaga tylko na czas jednego cyklu (nie na dysk).
_not_built_this_cycle = False


def pit_remaining_sec() -> float | None:
    """Sekundy do expires_at; None = brak aktywnego timera pitu."""
    expires = _parse_expires(_load_state().get("expires_at"))
    if expires is None:
        return None
    return (expires - datetime.now()).total_seconds()


def notify_and_clear_expired_pit() -> bool:
    """Timer minął → INFO + @everyone na Discord, wyczyść stan. True = wygasł."""
    state = _load_state()
    expires = _parse_expires(state.get("expires_at"))
    if expires is None or expires > datetime.now():
        return False
    alliance = state.get("alliance") or "?"
    raw_kind = state.get("kind")
    if isinstance(raw_kind, str) and raw_kind in _KIND_LABELS:
        kind_label = _KIND_LABELS[raw_kind]  # type: ignore[index]
    elif isinstance(raw_kind, str) and raw_kind:
        kind_label = raw_kind
    else:
        kind_label = "?"
    logger.info(
        "@everyone\nalliance_pit — pit zniknął (sojusz: %s, kind: %s)",
        alliance,
        kind_label,
    )
    _save_state(_empty_state())
    return True


def clear_expired_pit() -> None:
    """Jeśli expires_at minął — powiadom (Discord) i wyczyść stan pitu."""
    notify_and_clear_expired_pit()


def reset_not_built_pit() -> None:
    """Na start cyklu: pozwól znowu sprawdzić not_built w UI."""
    global _not_built_this_cycle
    _not_built_this_cycle = False


def force_clear_pit() -> None:
    """Reset z panelu WWW — wyczyść cały stan pitu."""
    global _not_built_this_cycle
    _not_built_this_cycle = False
    _save_state(_empty_state())
    logger.warning("alliance_pit — ręcznie wyczyszczono stan pitu")


def pit_status_for_ui() -> tuple[str | None, float | None]:
    """(PitPhase, remaining_sec) dla panelu WWW."""
    state = _load_state()
    phase = _normalize_phase(state.get("phase") or state.get("status"))
    expires = _parse_expires(state.get("expires_at"))
    if expires is None:
        return phase, None
    return phase, (expires - datetime.now()).total_seconds()


def pit_heroes_in_pit_for_ui() -> list[str]:
    """Lista uid/nick z in_pit (pusta gdy brak) — do dialogu w panelu WWW."""
    state = _load_state()
    raw = state.get("in_pit") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def pit_meta_for_ui() -> tuple[str | None, str | None]:
    """
    (sojusz, rodzaj) dla panelu WWW.

    sojusz — nazwa z JSON; rodzaj — etykieta PL (złoto/…) albo surowy kind.
    Brak danych → (None, None) albo jedno None.
    """
    state = _load_state()
    alliance = state.get("alliance")
    if not isinstance(alliance, str) or not alliance:
        alliance_out: str | None = None
    else:
        alliance_out = alliance

    raw_kind = state.get("kind")
    if isinstance(raw_kind, str) and raw_kind in _KIND_LABELS:
        kind_out: str | None = _KIND_LABELS[raw_kind]  # type: ignore[index]
    elif isinstance(raw_kind, str) and raw_kind:
        kind_out = raw_kind
    else:
        kind_out = None
    return alliance_out, kind_out


def alliance_pit() -> bool:
    """
    True = OK (send / skip / OCR).
    False = fail UI — manager wyłącza task u tego hero.
    """
    global _not_built_this_cycle

    if not manager.is_in_alliance():
        return True

    hero = Hero.current()
    if hero is None:
        logger.warning("alliance_pit — brak zalogowanego hero")
        return True

    if _not_built_this_cycle:
        return True

    state = _load_state()
    pit_alliance = state.get("alliance")
    if (
        isinstance(pit_alliance, str)
        and pit_alliance
        and hero.alliance
        and hero.alliance != pit_alliance
    ):
        return True

    if hero.key in _in_pit_set(state) and _timer_alive(state):
        return True

    nav = _navigate_to_pit()
    if nav == "nav_error":
        logger.warning("alliance_pit — błąd nawigacji")
        return False
    if nav == "no_alliance":
        return True
    if nav == "not_built":
        _not_built_this_cycle = True
        logger.warning("pit: not_built — skip akcji u kolejnych hero w tym cyklu")
        return True

    return _resolve_hero_view(hero)


def _navigate_to_pit() -> PitNavResult:
    """Terytorium sojuszu → zakładka centrów → klik zielonego plusa."""
    if not find_on_screen(_COLLECT_ALLY_RSS, timeout=_ALLY_MENU_CHECK_TIMEOUT):
        if not go_to_alliance_menu():
            return "nav_error"
        if not manager.is_in_alliance():
            return "no_alliance"
        stop_sleep(random.uniform(*_ACTION_DELAY))

        if not find_and_click(_ALLY_TERRITORY_MENU, timeout=_CLICK_TIMEOUT):
            logger.error("nie znaleziono ally_territory_menu.png")
            return "nav_error"
        stop_sleep(random.uniform(*_ACTION_DELAY))

    for _ in range(8):
        if not find_and_click(
            _HIDE_TAB,
            timeout=random.uniform(*_HIDE_TAB_TIMEOUT),
            threshold=0.999,
        ):
            break
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
    return "pit_exists"


def _resolve_hero_view(hero: Hero) -> bool:
    """Klik środka → can_gather / can_build / in_pit."""
    click_region(*_PIT_CENTER_REGION)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    found = wait_for_any_on_screen(
        [tpl for tpl, _ in _HERO_VIEW_TEMPLATES],
        threshold=_MATCH_THRESHOLD,
        timeout=_CLICK_TIMEOUT,
        poll_interval=_POLL_INTERVAL,
    )
    if found is None:
        logger.warning("nie znaleziono pit_gather / pit_build / pit_occupied")
        return False

    index, btn_rect = found
    view = _HERO_VIEW_TEMPLATES[index][1]
    state = _load_state()
    already_in = hero.key in _in_pit_set(state)

    if view == "can_gather":
        if already_in:
            logger.warning(
                "alliance_pit — %s in_pit, a UI=ZBIERZ — wysyłam ponownie",
                hero.nick,
            )
        return _hero_can_gather(hero, btn_rect)
    if view == "can_build":
        return _hero_can_build(hero, btn_rect)
    return _hero_in_pit(hero, btn_rect)


def _hero_can_gather(hero: Hero, btn_rect: tuple[int, int, int, int]) -> bool:
    """ZBIERZ: pit=built → OCR → send → in_pit."""
    click_region(*btn_rect)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    state = _load_state()
    _set_pit_phase(state, hero, phase="built")
    if not _timer_alive(state):
        _read_timer_into(state)

    if not find_and_click(_PIT_SEND, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono pit_send.png")
        _save_state(state)
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_RSS_CREATE_LEGION, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono rss_create_legion.png")
        _save_state(state)
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_LEGION_START, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono legion_start.png")
        _save_state(state)
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    _add_in_pit(state, hero)
    _save_state(state)
    return True


def _hero_can_build(hero: Hero, btn_rect: tuple[int, int, int, int]) -> bool:
    """BUDUJ: pit=constructing, kind z pitu lub OCR → send → in_pit."""
    state = _load_state()
    kind: PitKind | None = None
    raw_kind = state.get("kind")
    if isinstance(raw_kind, str) and raw_kind in _RSS_BY_PIT_KIND:
        kind = raw_kind  # type: ignore[assignment]
    else:
        bx, by, _bw, _bh = btn_rect
        pdx, pdy, pw, ph = _OCR_PANEL_OFFSET
        panel_region = (bx + pdx, by + pdy, pw, ph)
        panel_raw = (get_text(panel_region, _OCR_ALLOWLIST) or "").strip()
        panel_lower = panel_raw.lower()

        for marker, pit_kind in _KIND_MARKERS:
            if marker in panel_lower:
                kind = pit_kind
                break
        if kind is None:
            logger.warning("OCR pitu — nieznany rodzaj: %r", panel_raw[:120])

    _set_pit_phase(state, hero, phase="constructing", kind=kind)

    click_region(*btn_rect)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    if not find_and_click(_RSS_CREATE_LEGION, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono rss_create_legion.png")
        _save_state(state)
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
        logger.warning("can_build: brak kind — pomijam wybór surowca")

    if not find_and_click(_LEGION_START, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono legion_start.png")
        _save_state(state)
        return False
    stop_sleep(random.uniform(*_ACTION_DELAY))

    _add_in_pit(state, hero)
    _save_state(state)
    return True


def _hero_in_pit(hero: Hero, btn_rect: tuple[int, int, int, int]) -> bool:
    """WYŚWIETL: pit=built, hero już w picie → in_pit + OCR gdy trzeba."""
    click_region(*btn_rect)
    stop_sleep(random.uniform(*_ACTION_DELAY))

    state = _load_state()
    _set_pit_phase(state, hero, phase="built")
    _add_in_pit(state, hero)

    if not _timer_alive(state):
        if not _read_timer_into(state):
            logger.warning("alliance_pit — in_pit bez OCR timera")
            _save_state(state)
            if not find_and_click(_BACK_BUTTON, timeout=_CLICK_TIMEOUT):
                press_key("esc")
            return False

    _save_state(state)

    if not find_and_click(_BACK_BUTTON, timeout=_CLICK_TIMEOUT):
        logger.warning("nie znaleziono back_button.png — Escape")
        press_key("esc")
    stop_sleep(random.uniform(*_ACTION_DELAY))
    return True


# --- stan pitu (JSON) ---


def _empty_state() -> dict[str, Any]:
    return {
        "alliance": None,
        "phase": None,
        "expires_at": None,
        "in_pit": [],
        "kind": None,
    }


def _normalize_phase(raw: object) -> PitPhase | None:
    if not isinstance(raw, str) or not raw:
        return None
    if raw in ("not_built", "constructing", "built"):
        return raw  # type: ignore[return-value]
    return _LEGACY_PHASE.get(raw)


def _load_state() -> dict[str, Any]:
    raw = get_data(INFO_PATH, ALLIANCE_PIT_STATE, default=None)
    if not isinstance(raw, dict):
        return _empty_state()
    state = _empty_state()
    if isinstance(raw.get("alliance"), str):
        state["alliance"] = raw["alliance"]
    phase = _normalize_phase(raw.get("phase") or raw.get("status"))
    if phase is not None:
        state["phase"] = phase
    if isinstance(raw.get("expires_at"), str):
        state["expires_at"] = raw["expires_at"]
    if isinstance(raw.get("kind"), str):
        state["kind"] = raw["kind"]
    in_pit = raw.get("in_pit")
    if isinstance(in_pit, list):
        state["in_pit"] = [str(x) for x in in_pit]
    return state


def _save_state(state: dict[str, Any]) -> None:
    save_data(INFO_PATH, ALLIANCE_PIT_STATE, state)


def _in_pit_set(state: dict[str, Any]) -> set[str]:
    return set(state.get("in_pit") or [])


def _add_in_pit(state: dict[str, Any], hero: Hero) -> None:
    names = list(state.get("in_pit") or [])
    if hero.key not in names:
        names.append(hero.key)
        state["in_pit"] = names


def _set_pit_phase(
    state: dict[str, Any],
    hero: Hero,
    *,
    phase: PitPhase,
    kind: PitKind | None = None,
) -> None:
    """Ustaw globalną fazę pitu (+ sojusz przy pierwszym zapisie)."""
    if not state.get("alliance") and hero.alliance:
        state["alliance"] = hero.alliance
    state["phase"] = phase
    if kind is not None:
        state["kind"] = kind


def _parse_expires(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _timer_alive(state: dict[str, Any]) -> bool:
    expires = _parse_expires(state.get("expires_at"))
    return expires is not None and expires > datetime.now()


def _read_timer_into(state: dict[str, Any]) -> bool:
    """OCR timera → expires_at. True gdy udało się odczytać."""
    timer_raw = (get_text(_GATHER_TIMER_REGION, _TIMER_ALLOWLIST) or "").strip()
    match = _TIMER_RE.search(timer_raw)
    if match is None:
        logger.warning("OCR pitu — brak timera: %r", timer_raw[:120])
        return False
    h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
    lock_sec = float(h * 3600 + m * 60 + s)
    expires = datetime.now() + timedelta(seconds=lock_sec)
    state["expires_at"] = expires.isoformat(timespec="seconds")
    return True

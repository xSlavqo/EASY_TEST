"""
Wykrywanie aktywnego widoku gry — miasto vs mapa świata.

Publiczne: go_to_city, go_to_map, in_game, is_in_game.
"""

from __future__ import annotations

import random
import sys
import time
from enum import Enum
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import activate_window
from input import match_score, press_key, screenshot
from log import logger
from state.stop import sleep as stop_sleep

from .popups import dismiss_popups

IN_CITY_TEMPLATES = ("in_city.png", "in_city2.png")
ON_MAP_TEMPLATES = ("on_map.png", "on_map2.png")
# coord_picker 1920×1080 — ikona miasto/mapa (prawy dolny róg).
_VIEW_REGION = (1790, 962, 130, 117)

_DETECT_THRESHOLD = 0.99
_MAX_DETECT_ATTEMPTS = 10
_MAX_SWITCH_ATTEMPTS = 3
_UI_LOAD_DELAY = (1.0, 2.0)
_UI_SETTLE_DELAY = (1.0, 2.0)
_CITY_READY_TIMEOUT = 60.0
_CITY_READY_POLL = (0.5, 1.2)
_CITY_READY_MAX_ESC = 8


class GameView(Enum):
    CITY = "city"
    MAP = "map"
    UNKNOWN = "unknown"


def go_to_city() -> bool:
    """Przejdź do widoku miasta."""
    return _ensure_view(GameView.CITY)


def go_to_map() -> bool:
    """Przejdź do widoku mapy."""
    return _ensure_view(GameView.MAP)


def in_game() -> bool:
    """Czy jesteśmy w świecie gry (miasto LUB mapa)."""
    return _detect_view() is not GameView.UNKNOWN


def is_in_game(*, timeout: float = _CITY_READY_TIMEOUT) -> bool:
    """
    Po starcie / swapie: czekaj na miasto albo mapę.
    Brak → popup i szukaj dalej.
    Po timeout: kilka Esc, aż widać świat gry.
    Ekran swapa nie pasuje do szablonów — nie liczy się jako sukces.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        activate_window("game")
        view, _, _ = _score_view(screenshot(_VIEW_REGION))
        if view is not None:
            return True
        if dismiss_popups(timeout=0.5):
            continue
        stop_sleep(random.uniform(*_CITY_READY_POLL))

    logger.error("is_in_game — brak miasta/mapy przez %.0f s, próbuję Esc", timeout)
    for attempt in range(_CITY_READY_MAX_ESC):
        activate_window("game")
        press_key("esc")
        stop_sleep(random.uniform(*_UI_SETTLE_DELAY))
        view, _, _ = _score_view(screenshot(_VIEW_REGION))
        if view is not None:
            return True
        if dismiss_popups(timeout=0.8):
            view, _, _ = _score_view(screenshot(_VIEW_REGION))
            if view is not None:
                return True
    logger.error(
        "is_in_game — Esc nie odsłonił miasta ani mapy po %s próbach",
        _CITY_READY_MAX_ESC,
    )
    return False


def _score_view(screen) -> tuple[GameView | None, float, float]:
    """
    Porównaj jeden zrzut z szablonami miasta i mapy.

    Zwraca widok (CITY/MAP) albo None, gdy nic nie pasuje.
    Score (0–1) to „jak bardzo obrazek jest podobny”; im bliżej 1, tym pewniej.
    Gdy oba pasują, wygrywa wyższy score.
    """
    city_score = max(match_score(screen, t) for t in IN_CITY_TEMPLATES)
    map_score = max(match_score(screen, t) for t in ON_MAP_TEMPLATES)
    city_ok = city_score >= _DETECT_THRESHOLD
    map_ok = map_score >= _DETECT_THRESHOLD

    if city_ok and (not map_ok or city_score > map_score):
        return GameView.CITY, city_score, map_score
    if map_ok and (not city_ok or map_score > city_score):
        return GameView.MAP, city_score, map_score
    return None, city_score, map_score


def _detect_view(*, max_attempts: int = _MAX_DETECT_ATTEMPTS) -> GameView:
    """
    Znajdź widok miasta albo mapy (silnik pod in_game / go_to_*).

    Brak miasta/mapy → zamknij popup, potem Esc.
    UNKNOWN = nic nie znaleziono po wszystkich próbach.
    """
    last_city = last_map = 0.0
    for attempt in range(max_attempts):
        # Esc / spacja idą do okna z fokusem — bez tego klawisz trafia w panel bota.
        activate_window("game")
        screen = screenshot(_VIEW_REGION)
        view, city_score, map_score = _score_view(screen)
        last_city, last_map = city_score, map_score

        if view is not None:
            return view

        if attempt >= max_attempts - 1:
            break

        if dismiss_popups(timeout=0.8):
            logger.warning(
                "in_game — zamknięto popup(y), ponawiam (próba %s/%s)",
                attempt + 1,
                max_attempts,
            )
            continue

        logger.warning(
            "in_game — brak miasta/mapy, Esc (próba %s/%s, city=%.3f map=%.3f)",
            attempt + 1,
            max_attempts,
            city_score,
            map_score,
        )
        press_key("esc")
        stop_sleep(random.uniform(*_UI_SETTLE_DELAY))

    logger.error(
        "in_game — nie znaleziono miasta ani mapy po %s próbach (city=%.3f map=%.3f)",
        max_attempts,
        last_city,
        last_map,
    )
    return GameView.UNKNOWN


def _ensure_view(target: GameView) -> bool:
    """
    Doprowadź ekran do miasta albo mapy (silnik pod go_to_city / go_to_map).

    Najpierw odczytaj widok. Jeśli to nie ten, wciśnij spację (przełącza
    miasto ↔ mapa) i sprawdź ponownie.
    """
    view = _detect_view()
    if view is target:
        return True
    if view is GameView.UNKNOWN:
        return False

    for _ in range(_MAX_SWITCH_ATTEMPTS):
        press_key("space")
        stop_sleep(random.uniform(*_UI_LOAD_DELAY))
        if _detect_view() is target:
            return True
    logger.error(
        "nie udało się przejść do widoku %s po %s przełączeniach",
        target.value,
        _MAX_SWITCH_ATTEMPTS,
    )
    return False

"""
Wykrywanie aktywnego widoku gry — miasto vs mapa świata.
"""

from __future__ import annotations

import random
import sys
from enum import Enum
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import activate_window
from input import match_score, press_key, screenshot
from log import logger
from state.stop import sleep as stop_sleep

IN_CITY_TEMPLATES = ("in_city.png", "in_city2.png")
ON_MAP_TEMPLATES = ("on_map.png", "on_map2.png")
SETTING_BUTTON_TEMPLATE = _ROOT / "templates" / "navigation" / "setting_button.png"

_DETECT_THRESHOLD = 0.99
_MAX_DETECT_ATTEMPTS = 10
_MAX_SWITCH_ATTEMPTS = 3
# Losowe pauzy — jak w game_launcher (uniform między min a max).
_UI_LOAD_DELAY = (1.0, 2.0)  # po spacji — ładowanie widoku miasto/map
_UI_SETTLE_DELAY = (1.0, 2.0)  # po Esc — zamknięcie overlay / powrót UI


class GameView(Enum):
    CITY = "city"
    MAP = "map"
    UNKNOWN = "unknown"


def switch_view() -> None:
    """Przełącz widok miasto ↔ mapa (spacja)."""
    press_key("space")
    stop_sleep(random.uniform(*_UI_LOAD_DELAY))


def detect_view(*, max_attempts: int = _MAX_DETECT_ATTEMPTS) -> GameView:
    """
    Określ, czy gra pokazuje widok miasta czy mapy.

    Gdy żaden szablon nie pasuje (lub remis score), naciśnij Esc i spróbuj ponownie.
    Gdy miasto/mapa pasuje, ale widać setting_button — Esc (zamknięcie ustawień) i weryfikacja ponownie.
    Gdy oba pasują naraz, wybierz widok z wyższym score.
    Zwraca GameView.UNKNOWN po wyczerpaniu prób.
    """
    logger.info("detect_view START max_attempts=%s", max_attempts)
    last_city = last_map = 0.0
    # Esc / spacja idą do okna z fokusem — bez tego klawisz trafia w panel bota.
    logger.info("detect_view → activate_window(game) [przed pętlą]")
    activate_window("game")
    logger.info("detect_view ← activate_window(game) [przed pętlą]")
    for attempt in range(max_attempts):
        logger.info("detect_view próba %s/%s → screenshot + match", attempt + 1, max_attempts)
        screen = screenshot()
        city_score = max(match_score(screen, t) for t in IN_CITY_TEMPLATES)
        map_score = max(match_score(screen, t) for t in ON_MAP_TEMPLATES)
        last_city, last_map = city_score, map_score
        logger.info(
            "detect_view próba %s/%s city=%.3f map=%.3f (próg=%.2f)",
            attempt + 1,
            max_attempts,
            city_score,
            map_score,
            _DETECT_THRESHOLD,
        )

        city_ok = city_score >= _DETECT_THRESHOLD
        map_ok = map_score >= _DETECT_THRESHOLD
        if city_ok and not map_ok:
            view = GameView.CITY
        elif map_ok and not city_ok:
            view = GameView.MAP
        elif city_ok and map_ok and city_score != map_score:
            view = GameView.CITY if city_score > map_score else GameView.MAP
        else:
            view = None

        if view is not None:
            logger.info("detect_view widok=%s — sprawdzam setting_button", view.value)
            # Ustawienia otwarte nad miastem/mapą — zamknij Esc i potwierdź widok jeszcze raz.
            if match_score(screen, SETTING_BUTTON_TEMPLATE) >= _DETECT_THRESHOLD:
                logger.info("detect_view — setting_button widoczny, Esc")
                if attempt < max_attempts - 1:
                    activate_window("game")
                    press_key("esc")
                    stop_sleep(random.uniform(*_UI_SETTLE_DELAY))
                    continue
                logger.error(
                    "detect_view — ustawienia nadal otwarte po %s próbach (city=%.3f map=%.3f)",
                    max_attempts,
                    city_score,
                    map_score,
                )
                return GameView.UNKNOWN
            logger.info("detect_view OK = %s", view.value)
            return view

        if attempt < max_attempts - 1:
            logger.info("detect_view — brak widoku, Esc i retry")
            activate_window("game")
            press_key("esc")
            stop_sleep(random.uniform(*_UI_SETTLE_DELAY))

    logger.error(
        "detect_view — nie znaleziono miasta ani mapy po %s próbach (city=%.3f map=%.3f)",
        max_attempts,
        last_city,
        last_map,
    )
    return GameView.UNKNOWN


def in_game() -> bool:
    """Czy jesteśmy w świecie gry (miasto LUB mapa). Zamyka też ustawienia (setting_button)."""
    logger.info("in_game START → detect_view()")
    view = detect_view()
    ok = view is not GameView.UNKNOWN
    logger.info("in_game ← detect_view()=%s → %s", view.value, ok)
    return ok


def go_to_city() -> bool:
    """Przejdź do widoku miasta. Zwraca True, gdy miasto jest aktywne (bez ustawień)."""
    return _ensure_view(GameView.CITY)


def go_on_map() -> bool:
    """Przejdź do widoku mapy. Zwraca True, gdy mapa jest aktywna (bez ustawień)."""
    return _ensure_view(GameView.MAP)


def _ensure_view(target: GameView) -> bool:
    view = detect_view()
    if view is target:
        return True
    if view is GameView.UNKNOWN:
        return False

    for _ in range(_MAX_SWITCH_ATTEMPTS):
        switch_view()
        if detect_view() is target:
            return True
    logger.error(
        "nie udało się przejść do widoku %s po %s przełączeniach",
        target.value,
        _MAX_SWITCH_ATTEMPTS,
    )
    return False


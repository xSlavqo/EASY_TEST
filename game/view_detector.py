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

from .popups import dismiss_popups

IN_CITY_TEMPLATES = ("in_city.png", "in_city2.png")
ON_MAP_TEMPLATES = ("on_map.png", "on_map2.png")
SETTING_BUTTON_TEMPLATE = _ROOT / "templates" / "navigation" / "setting_button.png"

_DETECT_THRESHOLD = 0.99
_MAX_DETECT_ATTEMPTS = 10
_MAX_SWITCH_ATTEMPTS = 3
# Losowe pauzy — jak w game_launcher (uniform między min a max).
_UI_LOAD_DELAY = (1.0, 2.0)  # po spacji — ładowanie widoku miasto/map
_UI_SETTLE_DELAY = (1.0, 2.0)  # po Esc — zamknięcie overlay / powrót UI
# Pierwsze trafienie miasta/mapy → pauza → drugie sprawdzenie (potwierdzenie).
_VIEW_CONFIRM_DELAY = (2.0, 3.0)


class GameView(Enum):
    CITY = "city"
    MAP = "map"
    UNKNOWN = "unknown"


def switch_view() -> None:
    """Przełącz widok miasto ↔ mapa (spacja)."""
    press_key("space")
    stop_sleep(random.uniform(*_UI_LOAD_DELAY))


def _score_view(screen) -> tuple[GameView | None, float, float]:
    """
    Odczytaj widok z jednego screenshota.
    Zwraca (view|None, city_score, map_score). None = brak miasta/mapy.
    """
    city_score = max(match_score(screen, t) for t in IN_CITY_TEMPLATES)
    map_score = max(match_score(screen, t) for t in ON_MAP_TEMPLATES)

    city_ok = city_score >= _DETECT_THRESHOLD
    map_ok = map_score >= _DETECT_THRESHOLD
    if city_ok and not map_ok:
        view: GameView | None = GameView.CITY
    elif map_ok and not city_ok:
        view = GameView.MAP
    elif city_ok and map_ok and city_score != map_score:
        view = GameView.CITY if city_score > map_score else GameView.MAP
    else:
        view = None
    return view, city_score, map_score


def _settings_open(screen) -> bool:
    return match_score(screen, SETTING_BUTTON_TEMPLATE) >= _DETECT_THRESHOLD


def detect_view(*, max_attempts: int = _MAX_DETECT_ATTEMPTS) -> GameView:
    """
    Określ, czy gra pokazuje widok miasta czy mapy.

    Gdy brak miasta/mapy: najpierw znane popupy (dismiss_popups), potem Esc.
    Gdy miasto/mapa pasuje, ale widać setting_button — Esc i weryfikacja ponownie.
    Gdy widok pasuje (bez ustawień): poczekaj 2–3 s i potwierdź drugim sprawdzeniem;
    w trakcie potwierdzenia zamykane są wyskakujące popupy.
    Gdy oba pasują naraz, wybierz widok z wyższym score.
    Zwraca GameView.UNKNOWN po wyczerpaniu prób.
    """
    last_city = last_map = 0.0
    # Esc / spacja idą do okna z fokusem — bez tego klawisz trafia w panel bota.
    activate_window("game")
    for attempt in range(max_attempts):
        screen = screenshot()
        view, city_score, map_score = _score_view(screen)
        last_city, last_map = city_score, map_score

        if view is not None:
            # Ustawienia otwarte nad miastem/mapą — zamknij Esc i potwierdź widok jeszcze raz.
            if _settings_open(screen):
                logger.warning(
                    "detect_view — setting_button otwarty, Esc (próba %s/%s)",
                    attempt + 1,
                    max_attempts,
                )
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

            # Pierwsze trafienie — poczekaj i potwierdź; w trakcie mogą wyskoczyć popupy.
            confirm_wait = random.uniform(*_VIEW_CONFIRM_DELAY)
            popped_during_confirm = False
            elapsed = 0.0
            while elapsed < confirm_wait:
                slice_ = min(0.6, confirm_wait - elapsed)
                stop_sleep(slice_)
                elapsed += slice_
                activate_window("game")
                if dismiss_popups(timeout=0.5):
                    logger.warning(
                        "detect_view — popup podczas potwierdzenia, ponawiam (próba %s/%s)",
                        attempt + 1,
                        max_attempts,
                    )
                    popped_during_confirm = True
                    break

            if popped_during_confirm:
                if attempt >= max_attempts - 1:
                    break
                continue

            screen2 = screenshot()
            view2, _, _ = _score_view(screen2)
            if view2 is view and not _settings_open(screen2):
                return view

            logger.warning(
                "detect_view — brak potwierdzenia widoku %s po %.1fs (próba %s/%s)",
                view.value,
                confirm_wait,
                attempt + 1,
                max_attempts,
            )
            if attempt >= max_attempts - 1:
                break
            # Dalej ta sama ścieżka co przy braku widoku: popup → Esc.
            # (nie return — wpadamy w blok poniżej)

        if attempt < max_attempts - 1:
            # Najpierw znane X — Esc nie zawsze zamyka custom popup.
            # dismiss_popups sam zamyka kilka z rzędu (max 5), gdy po jednym
            # wyskakuje kolejny; ta pętla detect_view też ponawia przy wolnym UI.
            activate_window("game")
            if dismiss_popups(timeout=0.8):
                logger.warning(
                    "detect_view — zamknięto popup(y), ponawiam (próba %s/%s)",
                    attempt + 1,
                    max_attempts,
                )
                continue

            logger.warning(
                "detect_view — brak miasta/mapy city=%.3f map=%.3f, Esc (próba %s/%s)",
                city_score,
                map_score,
                attempt + 1,
                max_attempts,
            )
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
    """Czy jesteśmy w świecie gry (miasto LUB mapa), potwierdzone po ~2–3 s. Zamyka popupy i ustawienia."""
    return detect_view() is not GameView.UNKNOWN


def go_to_city() -> bool:
    """Przejdź do widoku miasta. True = miasto aktywne i potwierdzone (bez ustawień)."""
    return _ensure_view(GameView.CITY)


def go_on_map() -> bool:
    """Przejdź do widoku mapy. True = mapa aktywna i potwierdzona (bez ustawień)."""
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


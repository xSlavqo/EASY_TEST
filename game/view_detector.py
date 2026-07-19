"""
Wykrywanie aktywnego widoku gry — miasto vs mapa świata.
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

from input import match_score, press_key, screenshot

IN_CITY_TEMPLATE = "in_city.png"
ON_MAP_TEMPLATE = "on_map.png"

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


def _pause(lo: float = 0.4, hi: float = 0.9) -> None:
    """Losowa pauza między krokami."""
    time.sleep(random.uniform(lo, hi))


def switch_view() -> None:
    """Przełącz widok miasto ↔ mapa (spacja)."""
    press_key("space")
    _pause(*_UI_LOAD_DELAY)


def _capture_view_screen():
    """Zrzut ekranu do porównania szablonów miasto/map."""
    return screenshot()


def _view_from_scores(city_score: float, map_score: float) -> GameView | None:
    city_ok = city_score >= _DETECT_THRESHOLD
    map_ok = map_score >= _DETECT_THRESHOLD

    if city_ok and not map_ok:
        return GameView.CITY
    if map_ok and not city_ok:
        return GameView.MAP
    if city_ok and map_ok:
        if city_score > map_score:
            return GameView.CITY
        if map_score > city_score:
            return GameView.MAP
    return None


def detect_view(*, max_attempts: int = _MAX_DETECT_ATTEMPTS) -> GameView:
    """
    Określ, czy gra pokazuje widok miasta czy mapy.

    Gdy żaden szablon nie pasuje (lub remis score), naciśnij Esc i spróbuj ponownie.
    Gdy oba pasują naraz, wybierz widok z wyższym score.
    Zwraca GameView.UNKNOWN po wyczerpaniu prób.
    """
    for attempt in range(max_attempts):
        screen = _capture_view_screen()
        city_score = match_score(screen, IN_CITY_TEMPLATE)
        map_score = match_score(screen, ON_MAP_TEMPLATE)
        view = _view_from_scores(city_score, map_score)
        if view is not None:
            return view

        if attempt < max_attempts - 1:
            press_key("esc")
            _pause(*_UI_SETTLE_DELAY)

    return GameView.UNKNOWN


def in_game() -> bool:
    """Czy jesteśmy w świecie gry (miasto LUB mapa). detect_view robi ESC-retry."""
    return detect_view() is not GameView.UNKNOWN


def go_to_city() -> bool:
    """Przejdź do widoku miasta. Zwraca True, gdy miasto jest aktywne."""
    return _ensure_view(GameView.CITY)


def go_on_map() -> bool:
    """Przejdź do widoku mapy. Zwraca True, gdy mapa jest aktywna."""
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
    return False


def run_test() -> None:
    """Test wykrywania widoku: detect → switch → detect."""
    print("Wykrywanie biezacego widoku...")
    before = detect_view()
    print(f"Przed: {before.value}")

    print("Przelaczanie widoku (spacja)...")
    switch_view()

    print("Wykrywanie po przelaczeniu...")
    after = detect_view()
    print(f"Po:    {after.value}")

    if before is not GameView.UNKNOWN and after is not GameView.UNKNOWN:
        if before is after:
            print("Uwaga: widok sie nie zmienil — sprawdz gre lub szablony.")
        else:
            print("OK — widok sie zmienil.")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    run_test()

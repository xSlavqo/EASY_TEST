"""
Zarządzanie postaciami — wykrywanie zalogowanego, visited w cyklu, zamiana w menu.
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import click_region, find_and_click, find_on_screen, match_score, screenshot
from log import logger
from state.stop import check_stop, request_stop, sleep as stop_sleep

from .navigation import go_to_setting

_TEMPLATES_DIR = _ROOT / "templates"
_HEROES_DIR = _TEMPLATES_DIR / "heroes"
_MAIN_AVATAR = "main.png"
_SWAP_AVATAR = "swap.png"

_NAV_DIR = _TEMPLATES_DIR / "navigation"
_HERO_SWAP_MENU = _NAV_DIR / "in_hero_swap_menu.png"
_HERO_SWAP_CONFIRM = _NAV_DIR / "hero_swap_confirm.png"

# Hero swap menu — region z coord_picker (1920×1080).
_HERO_SWAP_MENU_REGION = (51, 589, 272, 62)
_REGION_CLICK_MARGIN = 0.15
_SWAP_MENU_CONFIRM_TIMEOUT = 30.0

MATCH_THRESHOLD = 0.99
_CURRENT_HERO_TIMEOUT = 60.0
_CURRENT_HERO_POLL = 5.0
_STEP_DELAY = (0.5, 1.0)
_MAX_HERO_MISS = 3
# swap.png to landmark — klikamy w prawo, we wpis bohatera obok awatara.
_SWAP_CLICK_OFFSET_X = (150, 250)
_SWAP_LOOKUP_TIMEOUT = 2.0
_SWAP_CONFIRM_TIMEOUT = 30.0


class Hero:
    """Jedna postać — awatary main/swap oraz stan logged_in i visited."""

    def __init__(self, hero_id: str, main: Path, swap: Path | None) -> None:
        self.id = hero_id
        self.main = main
        self.swap = swap
        self.logged_in = False
        self.visited = False


class HeroManager:
    """Bohaterowie z dysku + operacje na nich."""

    def __init__(self, heroes: list[Hero]) -> None:
        self.heroes = heroes
        self._miss_streak = 0

    @property
    def visited_ids(self) -> list[str]:
        return sorted(hero.id for hero in self.heroes if hero.visited)

    def current_hero(
        self,
        *,
        timeout: float = _CURRENT_HERO_TIMEOUT,
        poll: float = _CURRENT_HERO_POLL,
    ) -> bool:
        """Wykryj main.png na ekranie, ustaw logged_in. Zwraca True/False."""
        deadline = time.monotonic() + timeout
        while True:
            check_stop()
            detected: Hero | None = None
            try:
                screen = screenshot()
                best_score = MATCH_THRESHOLD
                for hero in self.heroes:
                    score = match_score(screen, hero.main)
                    if score >= best_score:
                        best_score = score
                        detected = hero
            except Exception:
                pass

            if detected is not None:
                for hero in self.heroes:
                    hero.logged_in = hero is detected
                self._miss_streak = 0
                logger.info("zalogowano %s", detected.id)
                return True

            if time.monotonic() >= deadline:
                for hero in self.heroes:
                    hero.logged_in = False
                self._miss_streak += 1
                logger.error(
                    "nie wykryto bohatera (%s/%s)",
                    self._miss_streak,
                    _MAX_HERO_MISS,
                )
                if self._miss_streak >= _MAX_HERO_MISS:
                    logger.error(
                        "przekroczono limit %s nieudanych wykryć bohatera — zatrzymuję bota",
                        _MAX_HERO_MISS,
                    )
                    request_stop()
                return False

            stop_sleep(poll)

    def hero_visited(self) -> None:
        """Oznacz zalogowanego bohatera jako odwiedzonego."""
        for hero in self.heroes:
            if hero.logged_in:
                hero.visited = True
                return
        logger.error("hero_visited — brak zalogowanego bohatera")

    def reset_all_hero_visited(self) -> None:
        """Wyzeruj visited u wszystkich — po zakończeniu cyklu."""
        for hero in self.heroes:
            hero.visited = False

    def swap_hero(self) -> bool | None:
        """
        Zamień postać, gdy są nieodwiedzeni.

        True — swap OK, None — brak kogo odwiedzić (koniec cyklu), False — błąd.
        """
        if not _HERO_SWAP_CONFIRM.is_file():
            logger.error("swap_hero — brak %s", _HERO_SWAP_CONFIRM)
            return False

        candidates = [hero for hero in self.heroes if not hero.visited]
        if not candidates:
            logger.info(
                "swap_hero — brak nieodwiedzonych bohaterów (visited: %s)",
                self.visited_ids,
            )
            return None

        if not go_to_setting():
            return False

        x, y, w, h = _HERO_SWAP_MENU_REGION
        click_region(x, y, w, h, margin=_REGION_CLICK_MARGIN)
        time.sleep(random.uniform(*_STEP_DELAY))

        if not find_on_screen(_HERO_SWAP_MENU, timeout=_SWAP_MENU_CONFIRM_TIMEOUT):
            logger.error(
                "nie udało się potwierdzić menu hero swap — brak in_hero_swap_menu.png po %s s",
                _SWAP_MENU_CONFIRM_TIMEOUT,
            )
            return False

        for hero in random.sample(candidates, len(candidates)):
            if hero.swap is None:
                continue

            if not find_and_click(
                hero.swap,
                timeout=_SWAP_LOOKUP_TIMEOUT,
                offset_x=random.randint(*_SWAP_CLICK_OFFSET_X),
            ):
                continue

            stop_sleep(random.uniform(*_STEP_DELAY))
            if find_and_click(_HERO_SWAP_CONFIRM, timeout=_SWAP_CONFIRM_TIMEOUT):
                logger.info("swap na %s", hero.id)
                return True

            logger.error("swap_hero — kliknięto %s, ale brak potwierdzenia", hero.id)
            return False

        remaining = [hero.id for hero in self.heroes if not hero.visited]
        logger.info(
            "swap_hero — brak widocznych nieodwiedzonych (visited: %s, pozostali: %s)",
            self.visited_ids,
            remaining,
        )
        return False


_heroes: list[Hero] = []
if _HEROES_DIR.is_dir():
    for _d in sorted(_HEROES_DIR.iterdir()):
        if not _d.is_dir():
            continue
        _main = _d / _MAIN_AVATAR
        if not _main.is_file():
            continue
        _swap_path = _d / _SWAP_AVATAR
        _swap = _swap_path if _swap_path.is_file() else None
        if _swap is None:
            logger.warning("brak swap.png dla %s — pomijany przy zamianie", _d.name)
        _heroes.append(Hero(_d.name, _main, _swap))

manager = HeroManager(_heroes)

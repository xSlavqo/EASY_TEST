"""
HeroManager — lista bohaterów z whitelist, visited, sklejka current_hero + swap.

current_hero → current_hero.py
swap / konto → swap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Pakiet jest w game/hero_manager/ → root projektu = 3 poziomy wyżej.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from log import logger
from state.keys import HEROES_VISITED
from state.store import INFO_PATH, get_data, save_data

from .current_hero import CurrentHero, NO_ALLIANCE
from .hero import Hero
from .swap import HeroSwap
from .whitelist import load_whitelist, set_hero_enabled


class HeroManager(CurrentHero, HeroSwap):
    """Bohaterowie z whitelist + operacje na nich."""

    def __init__(self, heroes: list[Hero]) -> None:
        self.heroes = heroes
        self._miss_streak = 0
        # Nick, na którego mieliśmy wejść w swap_hero; None = nie sprawdzaj.
        self._swap_target: str | None = None
        # False po 2× fail account_swap — do restartu procesu bota.
        self._account_swap_enabled = True
        # Przywróć visited z info.json (przeżywa restart procesu).
        raw = get_data(INFO_PATH, HEROES_VISITED, default=[])
        keys = {str(x) for x in raw} if isinstance(raw, list) else set()
        for hero in self.heroes:
            hero.visited = f"{hero.uid}/{hero.nick}" in keys
        if keys:
            logger.info("visited z dysku: %s", ", ".join(sorted(keys)))

    @property
    def visited_ids(self) -> list[str]:
        return sorted(hero.nick for hero in self.heroes if hero.visited)

    def disable_account_swap(self) -> None:
        """Wyłącz zamianę kont do ponownego uruchomienia bota."""
        self._account_swap_enabled = False
        logger.error("account_swap wyłączony — pomijany do ponownego uruchomienia bota")

    def consume_swap_mismatch(self) -> bool:
        """
        Po swapie: current != cel → wyłącz cel, True = pomiń taski.

        Trafiony cel albo brak celu (account_swap) → False.
        """
        target = self._swap_target
        self._swap_target = None
        if not target:
            return False
        current = None
        for hero in self.heroes:
            if hero.logged_in:
                current = hero
                break
        if current is not None and current.nick.casefold() == target.casefold():
            return False
        got = current.nick if current is not None else "?"
        logger.error(
            "swap_hero — cel %s, a jesteśmy na %s — wyłączam %s",
            target,
            got,
            target,
        )
        self.disable_hero(target)
        return True

    def disable_hero(self, nick: str) -> None:
        """enabled=False w pamięci i w heroes.json (jak wyłącznik w panelu)."""
        for hero in self.heroes:
            if hero.nick.casefold() != nick.casefold():
                continue
            hero.enabled = False
            set_hero_enabled(hero.nick, hero.uid, False)
            logger.error("whitelist: wyłączono %s uid=%s", hero.nick, hero.uid)
            return
        logger.error("disable_hero — brak %s na liście", nick)

    def hero_visited(self) -> None:
        """Oznacz zalogowanego bohatera jako odwiedzonego (+ zapis do info.json)."""
        for hero in self.heroes:
            if hero.logged_in:
                hero.visited = True
                save_data(
                    INFO_PATH,
                    HEROES_VISITED,
                    sorted(f"{h.uid}/{h.nick}" for h in self.heroes if h.visited),
                )
                return
        logger.error("hero_visited — brak zalogowanego bohatera")

    def reset_all_hero_visited(self) -> None:
        """Wyzeruj visited u wszystkich — po zakończeniu cyklu (+ info.json)."""
        for hero in self.heroes:
            hero.visited = False
        save_data(INFO_PATH, HEROES_VISITED, [])

    def is_visited(self) -> bool:
        """Czy zalogowany hero jest już oznaczony jako visited w tym cyklu."""
        for hero in self.heroes:
            if hero.logged_in:
                return hero.visited
        return False

    def is_in_alliance(self) -> bool:
        """True tylko gdy current_hero zapisał nazwę sojuszu (nie pusto, nie 'brak')."""
        for hero in self.heroes:
            if hero.logged_in:
                return bool(hero.alliance) and hero.alliance != NO_ALLIANCE
        return False

    def mark_not_in_alliance(self) -> None:
        """Ekran DOŁĄCZ — ten hero bez sojuszu; kolejne taski ally się pomijają."""
        for hero in self.heroes:
            if hero.logged_in:
                hero.alliance = NO_ALLIANCE
                logger.info(
                    "brak sojuszu u %s — taski sojuszu wyłączone u tej postaci",
                    hero.nick,
                )
                return
        logger.warning("mark_not_in_alliance — brak zalogowanego hero")

    def is_hero_enabled(self) -> bool:
        """Czy zalogowany hero jest włączony w panelu (nie zablokowany)."""
        for hero in self.heroes:
            if hero.logged_in:
                return hero.enabled
        return False

    def reload_from_whitelist(self) -> None:
        """
        Zsynchronizuj listę z heroes.json po dodaj/usuń/włącz/wyłącz.

        Istniejące obiekty zostają (logged_in, visited, pdw). Nowi — dopisani.
        """
        items = load_whitelist()
        old = {(hero.uid, hero.nick): hero for hero in self.heroes}
        raw = get_data(INFO_PATH, HEROES_VISITED, default=[])
        visited_keys = {str(x) for x in raw} if isinstance(raw, list) else set()

        new_list: list[Hero] = []
        for entry in items:
            key = (str(entry["uid"]), str(entry["nick"]))
            hero = old.get(key)
            if hero is None:
                hero = Hero(
                    str(entry["nick"]),
                    str(entry["uid"]),
                    enabled=bool(entry["enabled"]),
                )
                hero.visited = f"{hero.uid}/{hero.nick}" in visited_keys
            else:
                hero.enabled = bool(entry["enabled"])
            new_list.append(hero)

        self.heroes = new_list

    def _current_uid(self) -> str | None:
        """Uid konta zalogowanego bohatera."""
        for hero in self.heroes:
            if hero.logged_in:
                return hero.uid
        return None


_heroes = [
    Hero(entry["nick"], entry["uid"], enabled=bool(entry["enabled"]))
    for entry in load_whitelist()
]
if _heroes:
    logger.info("whitelist: %s postaci", len(_heroes))
else:
    logger.warning("whitelist pusta — current_hero nie dopasuje nicku")

manager = HeroManager(_heroes)

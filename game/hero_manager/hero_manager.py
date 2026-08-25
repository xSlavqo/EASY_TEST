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
from state.keys import HEROES_RUNTIME, HEROES_VISITED
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
        # Przywróć visited + runtime (alliance/pdw/…) z info.json.
        raw = get_data(INFO_PATH, HEROES_VISITED, default=[])
        keys = {str(x) for x in raw} if isinstance(raw, list) else set()
        for hero in self.heroes:
            hero.visited = hero.key in keys
        self._restore_heroes_runtime()

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
        current = Hero.current()
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
        hero = Hero.current()
        if hero is None:
            logger.error("hero_visited — brak zalogowanego bohatera")
            return
        hero.visited = True
        save_data(
            INFO_PATH,
            HEROES_VISITED,
            sorted(h.key for h in self.heroes if h.visited),
        )

    def reset_all_hero_visited(self) -> None:
        """Wyzeruj visited u wszystkich — po zakończeniu cyklu (+ info.json)."""
        for hero in self.heroes:
            hero.visited = False
        save_data(INFO_PATH, HEROES_VISITED, [])

    def is_visited(self) -> bool:
        """Czy zalogowany hero jest już oznaczony jako visited w tym cyklu."""
        hero = Hero.current()
        return hero.visited if hero is not None else False

    def is_in_alliance(self) -> bool:
        """True tylko gdy current_hero zapisał nazwę sojuszu (nie pusto, nie 'brak')."""
        hero = Hero.current()
        if hero is None:
            return False
        return bool(hero.alliance) and hero.alliance != NO_ALLIANCE

    def mark_not_in_alliance(self) -> None:
        """Ekran DOŁĄCZ — ten hero bez sojuszu; kolejne taski ally się pomijają."""
        hero = Hero.current()
        if hero is None:
            logger.warning("mark_not_in_alliance — brak zalogowanego hero")
            return
        hero.alliance = NO_ALLIANCE
        self.save_heroes_runtime()

    def save_heroes_runtime(self) -> None:
        """Zapisz alliance/hero_id/pdw (bez logged_in) do info.json."""
        rows: list[dict] = []
        for hero in self.heroes:
            rows.append(
                {
                    "uid": hero.uid,
                    "nick": hero.nick,
                    "alliance": hero.alliance,
                    "hero_id": hero.hero_id,
                    "pdw": hero.pdw,
                    "pdw_max": hero.pdw_max,
                }
            )
        save_data(INFO_PATH, HEROES_RUNTIME, rows)

    def _restore_heroes_runtime(self) -> None:
        """Wczytaj alliance/hero_id/pdw po restarcie procesu."""
        raw = get_data(INFO_PATH, HEROES_RUNTIME, default=[])
        if not isinstance(raw, list):
            return
        by_key = {
            (str(row.get("uid", "")), str(row.get("nick", ""))): row
            for row in raw
            if isinstance(row, dict)
        }
        for hero in self.heroes:
            row = by_key.get((hero.uid, hero.nick))
            if row is None:
                continue
            alliance = row.get("alliance")
            hero.alliance = str(alliance) if alliance is not None else None
            hero_id = row.get("hero_id")
            hero.hero_id = str(hero_id) if hero_id is not None else None
            pdw = row.get("pdw")
            hero.pdw = int(pdw) if isinstance(pdw, int) else None
            pdw_max = row.get("pdw_max")
            hero.pdw_max = int(pdw_max) if isinstance(pdw_max, int) else None

    def logged_in_hero(self) -> Hero | None:
        """Bieżąca postać po current_hero(), albo None."""
        return Hero.current()

    def is_hero_enabled(self) -> bool:
        """Czy zalogowany hero jest włączony w panelu (nie zablokowany)."""
        hero = Hero.current()
        return hero.enabled if hero is not None else False

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
            tasks = dict(entry.get("tasks", {}))
            rss_level = int(entry.get("gather_rss_level", 8))
            if hero is None:
                hero = Hero(
                    str(entry["nick"]),
                    str(entry["uid"]),
                    enabled=bool(entry["enabled"]),
                    tasks=tasks,
                    gather_rss_level=rss_level,
                )
                hero.visited = hero.key in visited_keys
            else:
                hero.enabled = bool(entry["enabled"])
                hero.tasks = tasks
                hero.gather_rss_level = rss_level
            new_list.append(hero)

        self.heroes = new_list
        current = Hero.current()
        if current is not None and current not in new_list:
            Hero.clear_logged_in()

    def _current_uid(self) -> str | None:
        """Uid konta zalogowanego bohatera."""
        hero = Hero.current()
        return hero.uid if hero is not None else None


_heroes = [
    Hero(
        entry["nick"],
        entry["uid"],
        enabled=bool(entry["enabled"]),
        tasks=dict(entry.get("tasks", {})),
        gather_rss_level=int(entry.get("gather_rss_level", 8)),
    )
    for entry in load_whitelist()
]
if not _heroes:
    logger.warning("whitelist pusta — current_hero nie dopasuje nicku")

manager = HeroManager(_heroes)

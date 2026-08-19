"""
TaskManager — reguły i uruchamianie tasków u bieżącego hero.

Jedyna brama: can_run / run_on_current_hero.
HeroManager dostarcza kto jest zalogowany; tasks/*.py tylko klikają.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from game.hero_manager import manager
from game.hero_manager.hero import Hero
from game.hero_manager.whitelist import load_whitelist
from log import logger
from state.keys import (
    TASK_ALLIANCE_PIT,
    TASK_ALLIANCE_RSS,
    scount_sentry_post_schedule_id,
)
from state.schedule import is_due, schedule
from state.settings import settings
from state.task_defs import TASK_DEFS
from tasks.alliance_pit import alliance_pit, is_wave_active
from tasks.alliance_rss import alliance_rss
from tasks.gather_rss import gather_rss
from tasks.scount_sentry_post import scount_sentry_post

_SETTINGS_BY_TASK = {task.task_id: task.settings_key for task in TASK_DEFS}


def _hours_to_sec(hours: float) -> float:
    return max(0.0, float(hours)) * 3600.0


@dataclass(frozen=True)
class _TaskSpec:
    task_id: str
    fn: Callable[[], Any]
    require_alliance: bool = False
    due: Callable[[Hero], bool] | None = None
    on_success: Callable[[Hero], None] | None = None


def _schedule_ssp_cooldown(hero: Hero) -> None:
    schedule_id = scount_sentry_post_schedule_id(hero.uid, hero.nick)
    schedule(schedule_id, _hours_to_sec(settings.ssp_cooldown_h))


_TASK_SPECS: tuple[_TaskSpec, ...] = (
    _TaskSpec(
        "alliance_rss",
        alliance_rss,
        require_alliance=True,
        due=lambda _hero: is_due(TASK_ALLIANCE_RSS),
    ),
    _TaskSpec(
        "alliance_pit",
        alliance_pit,
        require_alliance=True,
        due=lambda _hero: is_due(TASK_ALLIANCE_PIT) or is_wave_active(),
    ),
    _TaskSpec(
        "scount_sentry_post",
        scount_sentry_post,
        due=lambda hero: is_due(scount_sentry_post_schedule_id(hero.uid, hero.nick)),
        on_success=_schedule_ssp_cooldown,
    ),
    _TaskSpec("gather_rss", gather_rss),
)


class TaskManager:
    """Sprawdza reguły i odpala taski u zalogowanego hero."""

    def __init__(self) -> None:
        self._done: set[str] = set()
        self._specs = _TASK_SPECS
        self._spec_by_id = {spec.task_id: spec for spec in self._specs}

    def reset_session(self) -> None:
        """Nowy hero po swapie — wyczyść flagi zrobionych tasków w tej sesji."""
        self._done.clear()

    def _sync_hero_from_whitelist(self, hero: Hero) -> None:
        """Odśwież tasks/enabled z heroes.json (zmiany z panelu WWW bez restartu bota)."""
        for entry in load_whitelist():
            if entry["uid"] == hero.uid and entry["nick"] == hero.nick:
                hero.enabled = bool(entry.get("enabled", True))
                hero.tasks = dict(entry.get("tasks") or {})
                return

    def is_enabled(self, task_id: str, hero: Hero) -> bool:
        """Global ON AND per-hero ON (brak klucza w hero.tasks = włączone)."""
        settings_key = _SETTINGS_BY_TASK.get(task_id)
        if not settings_key:
            return False
        if not bool(getattr(settings, settings_key)):
            return False
        return bool(hero.tasks.get(task_id, True))

    def has_any_task_enabled(self, hero: Hero | None = None) -> bool:
        """Czy hero ma choć jeden task włączony (global + per-hero), bez due/sojuszu."""
        hero = hero or manager.logged_in_hero()
        if hero is None:
            return False
        self._sync_hero_from_whitelist(hero)
        return any(self.is_enabled(spec.task_id, hero) for spec in self._specs)

    def can_run(self, task_id: str, hero: Hero) -> bool:
        """Czy task można teraz odpalić u tego hero."""
        if task_id in self._done:
            return False
        if not self.is_enabled(task_id, hero):
            return False
        spec = self._spec_by_id.get(task_id)
        if spec is None:
            return False
        if spec.require_alliance and not manager.is_in_alliance():
            return False
        if spec.due is not None and not spec.due(hero):
            return False
        return True

    def _enabled_task_labels(self, hero: Hero) -> list[str]:
        return [spec.task_id for spec in self._specs if self.is_enabled(spec.task_id, hero)]

    def has_any_runnable_work(self, hero: Hero) -> bool:
        """Czy hero ma choć jeden task do zrobienia teraz."""
        return any(self.can_run(spec.task_id, hero) for spec in self._specs)

    def run_on_current_hero(self) -> bool | None:
        """
        Odpal taski u zalogowanego hero.

        None — OK albo same pominięcia. False — fail taska (cykl robi restart).
        """
        hero = manager.logged_in_hero()
        if hero is None:
            logger.warning("run_on_current_hero — brak zalogowanego hero")
            return None

        self._sync_hero_from_whitelist(hero)
        enabled = self._enabled_task_labels(hero)
        if not enabled:
            logger.info(
                "task_manager — %s: brak włączonych tasków (global + per-hero)",
                hero.nick,
            )
            return None

        logger.info(
            "task_manager — %s: włączone taski: %s",
            hero.nick,
            ", ".join(enabled),
        )

        for spec in self._specs:
            if not self.can_run(spec.task_id, hero):
                if self.is_enabled(spec.task_id, hero):
                    logger.info("task %s pominięty (reguły: czas / sojusz / już zrobiony)", spec.task_id)
                continue

            result = spec.fn()
            ok = bool(result[0]) if isinstance(result, tuple) else bool(result)
            if not ok:
                logger.error("task %s nieudany", spec.task_id)
                return False

            self._done.add(spec.task_id)
            logger.info("task %s OK", spec.task_id)
            if spec.on_success is not None:
                spec.on_success(hero)

        return None


task_manager = TaskManager()

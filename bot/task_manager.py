"""
TaskManager — reguły i uruchamianie tasków u bieżącego hero.

run_tasks: włączone (global + per-hero) → due → odpal → CD / disable przy False.
Na końcu jedno podsumowanie INFO; szczegóły tylko error/warning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from game.hero_manager import manager
from game.hero_manager.hero import Hero
from game.hero_manager.whitelist import load_whitelist, set_hero_enabled, set_hero_task
from log import logger
from state.keys import alliance_rss_schedule_id, scount_sentry_post_schedule_id
from state.schedule import is_due, schedule
from state.settings import settings
from state.task_defs import TASK_DEFS
from tasks.alliance_pit import alliance_pit
from tasks.alliance_rss import alliance_rss
from tasks.gather_rss import gather_rss
from tasks.scount_sentry_post import scount_sentry_post


class TaskManager:
    """Sprawdza reguły i odpala taski u zalogowanego hero."""

    def run_tasks(self) -> bool:
        """
        Odpal włączone taski u zalogowanego hero.

        Zawsze True — cykl robi visited. False taska → wyłącz task (ew. całego hero).
        """
        hero = manager.logged_in_hero()
        if hero is None:
            logger.warning("run_tasks — brak zalogowanego hero")
            return True

        _sync_hero_from_whitelist(hero)
        enabled = [spec.task_id for spec in _TASK_SPECS if self.is_enabled(spec.task_id, hero)]
        if not enabled:
            logger.info("%s — brak włączonych tasków", hero.nick)
            return True

        ok_ids: list[str] = []
        failed_ids: list[str] = []
        skipped_cd: list[str] = []

        for spec in _TASK_SPECS:
            if not self.is_enabled(spec.task_id, hero):
                continue
            if not self.can_run(spec.task_id, hero):
                skipped_cd.append(spec.task_id)
                continue

            result = spec.fn()
            success = bool(result[0]) if isinstance(result, tuple) else bool(result)
            if not success:
                logger.error("task %s nieudany — wyłączam u %s", spec.task_id, hero.nick)
                self._disable_task_on_hero(hero, spec.task_id)
                failed_ids.append(spec.task_id)
                continue

            ok_ids.append(spec.task_id)
            if spec.cooldown_settings_key and spec.schedule_id_for is not None:
                hours = float(getattr(settings, spec.cooldown_settings_key))
                schedule(
                    spec.schedule_id_for(hero.uid, hero.nick),
                    _hours_to_sec(hours),
                )

        logger.info("%s", _summary_line(hero.nick, ok_ids, failed_ids, skipped_cd))
        return True

    def can_run(self, task_id: str, hero: Hero) -> bool:
        """Czy task można teraz odpalić u tego hero."""
        if not self.is_enabled(task_id, hero):
            return False
        spec = _SPEC_BY_ID.get(task_id)
        if spec is None:
            return False
        if spec.schedule_id_for is not None:
            if not is_due(spec.schedule_id_for(hero.uid, hero.nick)):
                return False
        return True

    def is_enabled(self, task_id: str, hero: Hero) -> bool:
        """Global ON AND per-hero ON (brak klucza w hero.tasks = włączone)."""
        settings_key = _SETTINGS_BY_TASK.get(task_id)
        if not settings_key:
            return False
        if not bool(getattr(settings, settings_key)):
            return False
        return bool(hero.tasks.get(task_id, True))

    def has_any_task_enabled(self, hero: Hero | None = None) -> bool:
        """Czy hero ma choć jeden task włączony (global + per-hero), bez due."""
        hero = hero or manager.logged_in_hero()
        if hero is None:
            return False
        _sync_hero_from_whitelist(hero)
        return any(self.is_enabled(spec.task_id, hero) for spec in _TASK_SPECS)

    def _disable_task_on_hero(self, hero: Hero, task_id: str) -> None:
        """Wyłącz task u hero (+ JSON). Ostatni task OFF → wyłącz całego hero."""
        hero.tasks[task_id] = False
        set_hero_task(hero.nick, hero.uid, task_id, False)
        still_on = any(self.is_enabled(spec.task_id, hero) for spec in _TASK_SPECS)
        if still_on:
            return
        hero.enabled = False
        set_hero_enabled(hero.nick, hero.uid, False)
        logger.error(
            "task_manager — %s: brak włączonych tasków — wyłączam hero",
            hero.nick,
        )


def _summary_line(
    nick: str,
    ok_ids: list[str],
    failed_ids: list[str],
    skipped_cd: list[str],
) -> str:
    """Jedna linia podsumowania po run_tasks."""
    if failed_ids:
        parts = [f"{nick} —"]
        if ok_ids:
            parts.append(f"OK: {', '.join(ok_ids)};")
        parts.append(f"błąd (wyłączono): {', '.join(failed_ids)}")
        if skipped_cd:
            parts.append(f"; CD: {', '.join(skipped_cd)}")
        return " ".join(parts)
    if ok_ids and not skipped_cd:
        return f"{nick} — wszystkie zadania OK ({', '.join(ok_ids)})"
    if ok_ids and skipped_cd:
        return (
            f"{nick} — OK: {', '.join(ok_ids)}; "
            f"pominięto CD: {', '.join(skipped_cd)}"
        )
    if skipped_cd:
        return f"{nick} — brak due tasków (CD: {', '.join(skipped_cd)})"
    return f"{nick} — brak tasków do wykonania"


# --- pomocnicze ---

_SETTINGS_BY_TASK = {task.task_id: task.settings_key for task in TASK_DEFS}


def _hours_to_sec(hours: float) -> float:
    return max(0.0, float(hours)) * 3600.0


def _sync_hero_from_whitelist(hero: Hero) -> None:
    """Odśwież tasks/enabled z heroes.json (zmiany z panelu WWW bez restartu bota)."""
    for entry in load_whitelist():
        if entry["uid"] == hero.uid and entry["nick"] == hero.nick:
            hero.enabled = bool(entry.get("enabled", True))
            hero.tasks = dict(entry.get("tasks") or {})
            hero.gather_rss_level = int(entry.get("gather_rss_level", 8))
            return


@dataclass(frozen=True)
class _TaskSpec:
    task_id: str
    fn: Callable[[], Any]
    cooldown_settings_key: str | None = None
    schedule_id_for: Callable[[str, str], str] | None = None


_TASK_SPECS: tuple[_TaskSpec, ...] = (
    _TaskSpec(
        "alliance_rss",
        alliance_rss,
        cooldown_settings_key="alliance_rss_cooldown_h",
        schedule_id_for=alliance_rss_schedule_id,
    ),
    _TaskSpec("alliance_pit", alliance_pit),
    _TaskSpec("gather_rss", gather_rss),
    _TaskSpec(
        "scount_sentry_post",
        scount_sentry_post,
        cooldown_settings_key="ssp_cooldown_h",
        schedule_id_for=scount_sentry_post_schedule_id,
    ),
)

_SPEC_BY_ID = {spec.task_id: spec for spec in _TASK_SPECS}

task_manager = TaskManager()

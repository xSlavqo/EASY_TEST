"""Wspólna lista tasków — używana w panelu WWW i heroes.json."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDef:
    """Jeden task: id w heroes.json, etykieta UI, klucz globalny w config.json."""

    task_id: str
    label: str
    settings_key: str


TASK_DEFS: tuple[TaskDef, ...] = (
    TaskDef("alliance_rss", "Odbierz surowce sojuszu", "alliance_rss_enabled"),
    TaskDef("alliance_pit", "Centrum zasobów przymierza", "alliance_pit_enabled"),
    TaskDef("gather_buff", "Buff zbierania", "gather_buff_enabled"),
    TaskDef("gather_rss", "Zbieranie RSS", "gather_rss_enabled"),
    TaskDef("scount_sentry_post", "Sentry Post (próby scouta)", "scount_sentry_post_enabled"),
)

TASK_IDS: frozenset[str] = frozenset(task.task_id for task in TASK_DEFS)

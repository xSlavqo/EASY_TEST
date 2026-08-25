"""
Wspólna lista tasków bota — panel WWW i heroes.json używają tych samych id.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDef:
    """Jeden task: id w JSON, etykieta w UI, klucz włącznika w config.json."""

    task_id: str  # np. "gather_rss" — w heroes.json i TaskManager
    label: str  # tekst na panelu WWW
    settings_key: str  # np. "gather_rss_enabled" w config.json


# Kolejność = kolejność w panelu i w TaskManager.
TASK_DEFS: tuple[TaskDef, ...] = (
    TaskDef("alliance_rss", "Odbierz surowce sojuszu", "alliance_rss_enabled"),
    TaskDef("alliance_pit", "Centrum zasobów przymierza", "alliance_pit_enabled"),
    TaskDef("gather_buff", "Buff zbierania", "gather_buff_enabled"),
    TaskDef("gather_rss", "Zbieranie RSS", "gather_rss_enabled"),
    TaskDef("scount_sentry_post", "Sentry Post (próby scouta)", "scount_sentry_post_enabled"),
)

# Szybkie sprawdzenie: czy string to znany task_id.
TASK_IDS: frozenset[str] = frozenset(task.task_id for task in TASK_DEFS)

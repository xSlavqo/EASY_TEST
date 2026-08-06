"""Stałe kluczy w data/info.json."""

BOT = "bot"
TASK_ALLIANCE_RSS = "task.alliance_rss"
TASK_ALLIANCE_PIT = "task.alliance_pit"

# Stan pitu z ostatniego odczytu (not_built / gather / building / occupied).
ALLIANCE_PIT_STATUS = "task.alliance_pit.status"

# Lista odwiedzonych w bieżącym cyklu: ["email/hero_id", ...].
HEROES_VISITED = "heroes.visited"

# Stary płaski format — migracja przy pierwszym odczycie bota.
LEGACY_SCHEDULE_NEXT_RUN_AT = "schedule.next_run_at"
LEGACY_SCHEDULE_LAST_RUN_AT = "schedule.last_cycle_at"


def schedule_next_run_key(entity_id: str) -> str:
    return f"schedule.{entity_id}.next_run_at"

"""Stałe kluczy w data/info.json."""

BOT = "bot"
TASK_ALLIANCE_RSS = "task.alliance_rss"

# Stary płaski format — migracja przy pierwszym odczycie bota.
LEGACY_SCHEDULE_NEXT_RUN_AT = "schedule.next_run_at"
LEGACY_SCHEDULE_LAST_RUN_AT = "schedule.last_cycle_at"


def schedule_next_run_key(entity_id: str) -> str:
    return f"schedule.{entity_id}.next_run_at"

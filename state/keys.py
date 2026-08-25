"""
Nazwy kluczy w data/info.json — żeby nie wpisywać stringów „z ręki” po projekcie.

Przykład: HEROES_VISITED → "heroes.visited".
"""

# Harmonogram całego cyklu bota.
BOT = "bot"

# Prefiksy / id tasków w harmonogramie i stanie.
TASK_ALLIANCE_RSS = "task.alliance_rss"
TASK_ALLIANCE_PIT = "task.alliance_pit"
TASK_SCOUNT_SENTRY_POST = "task.scount_sentry_post"

# Blob stanu pitu: alliance, phase, expires_at, in_pit, kind.
ALLIANCE_PIT_STATE = "task.alliance_pit.state"

# Runtime hero (alliance, hero_id, pdw) — bez logged_in.
HEROES_RUNTIME = "heroes.runtime"

# Lista odwiedzonych w bieżącym cyklu: ["uid/nick", ...].
HEROES_VISITED = "heroes.visited"

# Stary płaski format — migracja przy pierwszym odczycie bota.
LEGACY_SCHEDULE_NEXT_RUN_AT = "schedule.next_run_at"
LEGACY_SCHEDULE_LAST_RUN_AT = "schedule.last_cycle_at"


def schedule_next_run_key(entity_id: str) -> str:
    """Zbuduj klucz JSON na termin: schedule.<entity_id>.next_run_at."""
    return f"schedule.{entity_id}.next_run_at"


def scount_sentry_post_schedule_id(uid: str, nick: str) -> str:
    """Id harmonogramu SSP dla jednej postaci: task.scount_sentry_post.<uid>/<nick>."""
    return f"{TASK_SCOUNT_SENTRY_POST}.{uid}/{nick}"


def alliance_rss_schedule_id(uid: str, nick: str) -> str:
    """Id harmonogramu RSS sojuszu dla jednej postaci: task.alliance_rss.<uid>/<nick>."""
    return f"{TASK_ALLIANCE_RSS}.{uid}/{nick}"

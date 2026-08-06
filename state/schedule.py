"""Harmonogram entity — persystencja w data/info.json."""

from __future__ import annotations

from datetime import datetime, timedelta

from log import logger

from .keys import (
    BOT,
    LEGACY_SCHEDULE_LAST_RUN_AT,
    LEGACY_SCHEDULE_NEXT_RUN_AT,
    schedule_next_run_key,
)
from .stop import sleep as stop_sleep
from .store import INFO_PATH, delete_data, get_data, save_data


def schedule(entity_id: str, wait_sec: float) -> datetime:
    """Zapisz next_run_at = teraz + wait_sec.

    wait_sec=0 → termin = teraz → entity od razu due (np. Reset cyklu w UI).
    """
    next_run = datetime.now() + timedelta(seconds=wait_sec)
    save_data(INFO_PATH, schedule_next_run_key(entity_id), next_run.isoformat(timespec="seconds"))
    logger.info("następne wysłanie o %s", next_run.strftime("%H:%M"))
    return next_run


def is_due(entity_id: str) -> bool:
    """True = brak harmonogramu lub termin minął (wpuszczaj)."""
    rem = remaining_sec(entity_id)
    return rem is None or rem <= 0


def remaining_sec(entity_id: str) -> float | None:
    """Sekundy do next_run_at; None = brak terminu; <=0 = już due."""
    if entity_id == BOT:
        if not get_data(INFO_PATH, schedule_next_run_key(BOT)):
            legacy_next = get_data(INFO_PATH, LEGACY_SCHEDULE_NEXT_RUN_AT)
            if legacy_next is not None:
                save_data(INFO_PATH, schedule_next_run_key(BOT), legacy_next)
                delete_data(INFO_PATH, LEGACY_SCHEDULE_NEXT_RUN_AT)
                delete_data(INFO_PATH, LEGACY_SCHEDULE_LAST_RUN_AT)

    raw = get_data(INFO_PATH, schedule_next_run_key(entity_id))
    if not isinstance(raw, str) or not raw:
        return None
    try:
        next_run = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return (next_run - datetime.now()).total_seconds()


def sleep_until_due(entity_id: str, *, log: bool = True) -> None:
    """Czekaj do zapisanego next_run_at; reaguje na reset harmonogramu w UI."""
    logged = False
    while True:
        rem = remaining_sec(entity_id)
        if rem is None or rem <= 0:
            return

        if log and not logged:
            total_sec = int(rem)
            hours, rest = divmod(total_sec, 3600)
            minutes, seconds = divmod(rest, 60)
            if hours:
                wait_label = f"{hours} h {minutes} min"
            elif minutes:
                wait_label = f"{minutes} min {seconds} s"
            else:
                wait_label = f"{seconds} s"
            next_run = datetime.now() + timedelta(seconds=rem)
            logger.info(
                "następne wysłanie o %s — za %s",
                next_run.strftime("%H:%M"),
                wait_label,
            )
            logged = True

        # Krótkie chunki — Reset w UI (schedule=0) od razu wychodzi z pętli.
        stop_sleep(min(rem, 1.0))

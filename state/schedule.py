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
    """Zapisz next_run_at = teraz + wait_sec."""
    next_run = datetime.now() + timedelta(seconds=wait_sec)
    save_data(INFO_PATH, schedule_next_run_key(entity_id), next_run.isoformat(timespec="seconds"))
    logger.info("następne wysłanie o %s", next_run.strftime("%H:%M"))
    return next_run


def is_due(entity_id: str) -> bool:
    """True = brak harmonogramu lub termin minął (wpuszczaj)."""
    if entity_id == BOT:
        if not get_data(INFO_PATH, schedule_next_run_key(BOT)):
            legacy_next = get_data(INFO_PATH, LEGACY_SCHEDULE_NEXT_RUN_AT)
            if legacy_next is not None:
                save_data(INFO_PATH, schedule_next_run_key(BOT), legacy_next)
                delete_data(INFO_PATH, LEGACY_SCHEDULE_NEXT_RUN_AT)
                delete_data(INFO_PATH, LEGACY_SCHEDULE_LAST_RUN_AT)

    raw = get_data(INFO_PATH, schedule_next_run_key(entity_id))
    if not isinstance(raw, str) or not raw:
        return True
    try:
        return datetime.now() >= datetime.fromisoformat(raw)
    except ValueError:
        return True


def sleep_until_due(entity_id: str, *, log: bool = True) -> None:
    """Czekaj do zapisanego next_run_at, jeśli termin jeszcze nie minął."""
    if is_due(entity_id):
        return

    raw = get_data(INFO_PATH, schedule_next_run_key(entity_id))
    if not isinstance(raw, str) or not raw:
        return
    try:
        next_run = datetime.fromisoformat(raw)
    except ValueError:
        return

    remaining = (next_run - datetime.now()).total_seconds()
    if remaining <= 0:
        return

    if log:
        total_sec = int(remaining)
        hours, rem = divmod(total_sec, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            wait_label = f"{hours} h {minutes} min"
        elif minutes:
            wait_label = f"{minutes} min {seconds} s"
        else:
            wait_label = f"{seconds} s"
        logger.info(
            "następne wysłanie o %s — za %s",
            next_run.strftime("%H:%M"),
            wait_label,
        )

    stop_sleep(remaining)

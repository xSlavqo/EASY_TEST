"""Pasek statusu (bot, cykl, pit) + logi."""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable

from nicegui import ui

from game.hero_manager import manager
from log import logger
from state.keys import (
    BOT,
    alliance_rss_schedule_id,
    scount_sentry_post_schedule_id,
)
from state.schedule import remaining_sec, schedule
from state.stop import is_stopped
from tasks.alliance_pit import (
    force_clear_pit,
    pit_heroes_in_pit_for_ui,
    pit_meta_for_ui,
    pit_status_for_ui,
)
from www.formatters import format_countdown, format_pit_status, format_pit_time

# Logi z wątku bota → historia; każda karta przeglądarki dogania nowe linie.
_LOG_LOCK = threading.Lock()
_LOG_ENTRIES: deque[tuple[int, str]] = deque(maxlen=800)
_LOG_SEQ = 0
_LOG_HANDLER_ATTACHED = False


def _soonest_per_hero_remaining(
    schedule_id_for: Callable[[str, str], str],
) -> float | None:
    """
    Odliczanie per-hero tasków: 0 jeśli któryś hero jest due,
    inaczej najbliższy przyszły termin wśród bohaterów.
    """
    soonest_future: float | None = None
    someone_due = False
    for hero in manager.heroes:
        rem = remaining_sec(schedule_id_for(hero.uid, hero.nick))
        if rem is None or rem <= 0:
            someone_due = True
            continue
        if soonest_future is None or rem < soonest_future:
            soonest_future = rem
    if someone_due:
        return 0.0
    return soonest_future


def _reset_all_hero_schedules(
    schedule_id_for: Callable[[str, str], str],
    label: str,
) -> None:
    """Reset harmonogramu u wszystkich bohaterów → od razu due."""
    for hero in manager.heroes:
        schedule(schedule_id_for(hero.uid, hero.nick), 0)
    logger.info("zresetowano harmonogram %s u wszystkich hero", label)


def _reset_all_ssp_schedules() -> None:
    _reset_all_hero_schedules(scount_sentry_post_schedule_id, "SSP")


def _reset_all_alliance_rss_schedules() -> None:
    _reset_all_hero_schedules(alliance_rss_schedule_id, "RSS sojuszu")


class _HistoryLogHandler(logging.Handler):
    """Zapisuje sformatowane linie do wspólnej historii (wątkowo bezpiecznie)."""

    def emit(self, record: logging.LogRecord) -> None:
        global _LOG_SEQ
        try:
            msg = self.format(record)
        except Exception:
            self.handleError(record)
            return
        with _LOG_LOCK:
            _LOG_SEQ += 1
            _LOG_ENTRIES.append((_LOG_SEQ, msg))


def ensure_log_handler() -> None:
    global _LOG_HANDLER_ATTACHED
    if _LOG_HANDLER_ATTACHED:
        return
    handler = _HistoryLogHandler()
    handler.setLevel(logging.INFO)
    logger.attach_handler(handler)
    _LOG_HANDLER_ATTACHED = True


def build_status_bar(
    on_start: Callable[[], None] | None,
    on_stop: Callable[[], None] | None,
) -> None:
    """Górny pasek: Start/Stop, cykl, pit, skróty RSS/SSP, visited."""
    with ui.card().classes("w-full bg-[#383838]"):
        with ui.row().classes("items-center gap-3 flex-wrap w-full"):
            bot_btn = ui.button("Start")

            def _toggle_bot() -> None:
                if is_stopped():
                    if on_start is not None:
                        on_start()
                else:
                    if on_stop is not None:
                        on_stop()
                _sync_bot_btn()

            bot_btn.on_click(_toggle_bot)

            def _sync_bot_btn() -> None:
                bot_btn.set_text("Start" if is_stopped() else "Stop (F9)")

            ui.separator().props("vertical")

            ui.label("cykl:").classes("text-grey")
            countdown_lbl = ui.label("—").classes("font-bold")
            ui.button("Reset", on_click=lambda: schedule(BOT, 0)).props("flat dense")

            ui.label("RSS:").classes("text-grey")
            alliance_rss_time_lbl = ui.label("—").classes("font-bold")
            ui.button("Reset", on_click=_reset_all_alliance_rss_schedules).props(
                "flat dense"
            )

            ui.label("SSP:").classes("text-grey")
            ssp_time_lbl = ui.label("—").classes("font-bold")
            ui.button("Reset", on_click=_reset_all_ssp_schedules).props("flat dense")

            ui.label("odwiedzeni:").classes("text-grey")
            visited_lbl = ui.label("0").classes("font-bold")

            def _clear_visited() -> None:
                manager.reset_all_hero_visited()
                logger.info("wyczyszczono listę odwiedzonych hero")
                visited_lbl.set_text("0")

            ui.button("Wyczyść", on_click=_clear_visited).props("flat dense")

        with ui.row().classes("items-center gap-3 flex-wrap w-full mt-1"):
            ui.label("Pit:").classes("text-grey")
            pit_status_lbl = ui.label("—").classes("font-bold")
            ui.label("czas:").classes("text-grey")
            pit_time_lbl = ui.label("—").classes("font-bold")
            ui.label("rodzaj:").classes("text-grey")
            pit_kind_lbl = ui.label("—").classes("font-bold")
            ui.label("sojusz:").classes("text-grey")
            pit_alliance_lbl = ui.label("—").classes("font-bold")
            ui.label("w picie:").classes("text-grey")
            pit_heroes_lbl = ui.label("—").classes("font-bold")
            ui.button("Reset", on_click=force_clear_pit).props("flat dense")

        def _sync_status() -> None:
            countdown_lbl.set_text(format_countdown(remaining_sec(BOT)))
            status, pit_rem = pit_status_for_ui()
            pit_time_lbl.set_text(format_pit_time(status, pit_rem))
            pit_status_lbl.set_text(format_pit_status(status, pit_rem))
            pit_alliance, pit_kind = pit_meta_for_ui()
            pit_kind_lbl.set_text(pit_kind or "—")
            pit_alliance_lbl.set_text(pit_alliance or "—")
            names = pit_heroes_in_pit_for_ui()
            if not names:
                pit_heroes_lbl.set_text("brak")
            else:
                pretty: list[str] = []
                for item in names:
                    if "/" in item:
                        _uid, nick = item.split("/", 1)
                        pretty.append(nick)
                    else:
                        pretty.append(item)
                pit_heroes_lbl.set_text(", ".join(pretty))
            alliance_rss_time_lbl.set_text(
                format_countdown(
                    _soonest_per_hero_remaining(alliance_rss_schedule_id)
                )
            )
            ssp_time_lbl.set_text(
                format_countdown(
                    _soonest_per_hero_remaining(scount_sentry_post_schedule_id)
                )
            )
            visited_lbl.set_text(str(len(manager.visited_ids)))
            _sync_bot_btn()

        ui.timer(0.25, _sync_status)


def build_logs_card() -> None:
    """Karta logów pod siatką herosów."""
    with ui.card().classes(
        "w-full flex flex-col min-h-48 md:min-h-64 bg-[#383838]"
    ):
        ui.label("Logi").classes("text-subtitle1")
        log_view = ui.log(max_lines=500).classes("w-full min-h-48 md:min-h-56")

        last_seq = 0

        with _LOG_LOCK:
            seed = list(_LOG_ENTRIES)
        for seq, msg in seed:
            log_view.push(msg)
            last_seq = seq

        def _drain_logs() -> None:
            nonlocal last_seq
            with _LOG_LOCK:
                fresh = [(s, m) for s, m in _LOG_ENTRIES if s > last_seq]
            for seq, msg in fresh:
                log_view.push(msg)
                last_seq = seq

        ui.timer(0.2, _drain_logs)

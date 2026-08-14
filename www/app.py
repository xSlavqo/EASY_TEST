"""Panel NiceGUI — settings, Start/Stop, odliczania, logi."""

from __future__ import annotations

import logging
import socket
import sys
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nicegui import app, ui

from game.hero_manager import manager
from log import logger
from state.keys import ALLIANCE_PIT_STATUS, BOT, TASK_ALLIANCE_PIT
from state.schedule import remaining_sec, schedule
from state.settings import settings
from state.stop import is_stopped
from state.store import INFO_PATH, get_data
from www.formatters import format_countdown, format_pit_status, format_pit_time


def _lan_ips() -> list[str]:
    """Lokalne adresy IPv4 (bez localhost) — do linku z telefonu / innego PC."""
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    if not ips:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if not ip.startswith("127."):
                    ips.append(ip)
        except OSError:
            pass
    return ips


def _log_panel_urls(port: int) -> None:
    """Wypisz w logu adresy, pod którymi panel jest dostępny w LAN."""
    logger.info("panel WWW: http://127.0.0.1:%s/ (tylko ten komputer)", port)
    try:
        name = socket.gethostname()
        logger.info("panel WWW: http://%s:%s/ (nazwa PC w sieci)", name, port)
    except OSError:
        pass
    for ip in _lan_ips():
        logger.info("panel WWW: http://%s:%s/ (telefon / inny PC w Wi‑Fi)", ip, port)

# (klucz w config.json, etykieta w panelu)
_CHECKS = (
    ("close_game_after_cycle", "Zamykaj grę po cyklu"),
    ("alliance_rss_enabled", "Odbierz surowce sojuszu"),
    ("alliance_pit_enabled", "Centrum zasobów przymierza"),
    ("gather_rss_enabled", "Zbieranie RSS"),
    ("gather_rss_gold", "RSS: złoto"),
    ("gather_rss_wood", "RSS: drewno"),
    ("gather_rss_ore", "RSS: ruda"),
)

_GATHER_RSS_LEVEL_MIN = 1
_GATHER_RSS_LEVEL_MAX = 10

# Logi z wątku bota → historia; każda karta przeglądarki dogania nowe linie.
_LOG_LOCK = threading.Lock()
_LOG_ENTRIES: deque[tuple[int, str]] = deque(maxlen=800)
_LOG_SEQ = 0
_LOG_HANDLER_ATTACHED = False


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


def _ensure_log_handler() -> None:
    global _LOG_HANDLER_ATTACHED
    if _LOG_HANDLER_ATTACHED:
        return
    handler = _HistoryLogHandler()
    handler.setLevel(logging.INFO)
    logger.attach_handler(handler)
    _LOG_HANDLER_ATTACHED = True


def run_www(
    on_ready: Callable[[], None] | None = None,
    on_start: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """Uruchom panel WWW (domyślnie dostępny w sieci lokalnej, bez otwierania przeglądarki)."""
    _ensure_log_handler()

    if on_ready is not None:
        app.on_startup(on_ready)

    app.on_startup(lambda: _log_panel_urls(port))

    @ui.page("/")
    def _index() -> None:
        ui.page_title("EASY_TEST — panel")
        ui.dark_mode().enable()
        ui.colors(primary="#2563eb")
        ui.query("body").classes("bg-[#2d2d2d]")

        # 1) Status+logi  2) Ustawienia
        with ui.row().classes(
            "w-full h-screen p-4 gap-4 items-stretch flex-nowrap bg-[#2d2d2d]"
        ):
            with ui.column().classes("flex-grow min-w-0 h-full gap-4"):
                # ── Status (lewo góra) ────────────────────────────────────
                with ui.card().classes("w-full bg-[#383838]"):
                    ui.label("Status").classes("text-subtitle1")

                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.label("czas do następnego cyklu:")
                        countdown_lbl = ui.label("—").classes("font-bold")
                        ui.button(
                            "Reset",
                            on_click=lambda: schedule(BOT, 0),
                        ).props("flat dense")

                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.label("czas do pitu:")
                        pit_time_lbl = ui.label("—").classes("font-bold")
                        ui.label("stan:")
                        pit_status_lbl = ui.label("—").classes("font-bold")
                        ui.button(
                            "Reset",
                            on_click=lambda: schedule(TASK_ALLIANCE_PIT, 0),
                        ).props("flat dense")

                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.label("odwiedzeni hero:")
                        visited_lbl = ui.label("0").classes("font-bold")

                        def _clear_visited() -> None:
                            manager.reset_all_hero_visited()
                            logger.info("wyczyszczono listę odwiedzonych hero")
                            visited_lbl.set_text("0")

                        ui.button("Wyczyść", on_click=_clear_visited).props(
                            "flat dense"
                        )

                    bot_btn = ui.button("Start").classes("mt-2")

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
                        bot_btn.set_text(
                            "Start" if is_stopped() else "Stop (F9)"
                        )

                    def _sync_status() -> None:
                        countdown_lbl.set_text(
                            format_countdown(remaining_sec(BOT))
                        )
                        raw_status = get_data(INFO_PATH, ALLIANCE_PIT_STATUS)
                        status = (
                            raw_status if isinstance(raw_status, str) else None
                        )
                        pit_rem = remaining_sec(TASK_ALLIANCE_PIT)
                        pit_time_lbl.set_text(
                            format_pit_time(status, pit_rem)
                        )
                        pit_status_lbl.set_text(
                            format_pit_status(status, pit_rem)
                        )
                        visited_lbl.set_text(str(len(manager.visited_ids)))
                        _sync_bot_btn()

                    ui.timer(0.25, _sync_status)

                # ── Logi (lewo, pod statusem) ─────────────────────────────
                with ui.card().classes(
                    "w-full flex-grow flex flex-col min-h-0 bg-[#383838]"
                ):
                    ui.label("Logi").classes("text-subtitle1")
                    log_view = ui.log(max_lines=500).classes(
                        "w-full flex-grow min-h-64"
                    )

                    last_seq = 0

                    with _LOG_LOCK:
                        seed = list(_LOG_ENTRIES)
                    for seq, msg in seed:
                        log_view.push(msg)
                        last_seq = seq

                    def _drain_logs() -> None:
                        nonlocal last_seq
                        with _LOG_LOCK:
                            fresh = [
                                (s, m)
                                for s, m in _LOG_ENTRIES
                                if s > last_seq
                            ]
                        for seq, msg in fresh:
                            log_view.push(msg)
                            last_seq = seq

                    ui.timer(0.2, _drain_logs)

            # ── Ustawienia (środek) ───────────────────────────────────────
            with ui.card().classes(
                "w-80 shrink-0 h-full overflow-auto bg-[#383838]"
            ):
                ui.label("Ustawienia").classes("text-subtitle1")
                for key, label in _CHECKS:

                    def _on_toggle(e, k: str = key) -> None:
                        setattr(settings, k, bool(e.value))

                    ui.checkbox(
                        label,
                        value=bool(getattr(settings, key)),
                        on_change=_on_toggle,
                    )

                with ui.row().classes("items-center gap-2 flex-wrap mt-2"):
                    ui.label("RSS: poziom")

                    def _on_level(e) -> None:
                        try:
                            level = int(e.value)
                        except (TypeError, ValueError):
                            return
                        level = max(
                            _GATHER_RSS_LEVEL_MIN,
                            min(_GATHER_RSS_LEVEL_MAX, level),
                        )
                        settings.gather_rss_level = level

                    ui.number(
                        value=int(settings.gather_rss_level),
                        min=_GATHER_RSS_LEVEL_MIN,
                        max=_GATHER_RSS_LEVEL_MAX,
                        step=1,
                        on_change=_on_level,
                    ).props("dense outlined").classes("w-24")

    ui.run(
        host=host,
        port=port,
        reload=False,
        show=False,  # nie otwieraj przeglądarki przy starcie
        title="EASY_TEST",
        favicon="🤖",
    )


if __name__ == "__main__":
    run_www()

"""Panel NiceGUI — status, siatka kart herosów, ustawienia, logi."""

from __future__ import annotations

import socket
import sys
from collections.abc import Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nicegui import app, ui

from log import logger
from www.heroes_panel import build_heroes_panel
from www.settings_panel import build_settings_panel
from www.status import build_logs_card, build_status_bar, ensure_log_handler


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


def run_www(
    on_ready: Callable[[], None] | None = None,
    on_start: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """Uruchom panel WWW (domyślnie dostępny w sieci lokalnej, bez otwierania przeglądarki)."""
    ensure_log_handler()

    if on_ready is not None:
        app.on_startup(on_ready)

    app.on_startup(lambda: _log_panel_urls(port))

    @ui.page("/")
    def _index() -> None:
        ui.page_title("EASY_TEST — panel")
        ui.dark_mode().enable()
        ui.colors(primary="#2563eb")
        ui.query("body").classes("bg-[#2d2d2d]")

        # PC: główna kolumna (status + karty + logi) | ustawienia
        # telefon: wszystko pod sobą
        with ui.row().classes(
            "w-full min-h-screen p-4 gap-4 items-start flex-col "
            "md:flex-row md:flex-nowrap bg-[#2d2d2d]"
        ):
            with ui.column().classes("w-full flex-grow min-w-0 gap-4"):
                build_status_bar(on_start, on_stop)
                refresh_heroes = build_heroes_panel()
                build_logs_card()
            build_settings_panel(on_global_task_change=refresh_heroes)

    ui.run(
        host=host,
        port=port,
        reload=False,
        show=False,
        title="EASY_TEST",
        favicon="🤖",
    )


if __name__ == "__main__":
    run_www()

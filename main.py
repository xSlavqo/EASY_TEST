"""Punkt wejścia — panel WWW, Discord, pętla bota."""

import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bot import run_cycle
from discord_bot import start_discord_bot
from game.hero_manager import manager
from log import logger
from state.keys import BOT
from state.schedule import sleep_until_due
from state.stop import (
    StopRequested,
    check_stop,
    clear_stop,
    is_stopped,
    request_stop,
    start_hotkey_listener,
)
from www.app import run_www


def _bot_loop() -> None:
    """Pętla bota — czeka na Start z UI, potem działa aż do Stop/F9 / fail cyklu."""
    while True:
        while is_stopped():
            time.sleep(0.1)
        try:
            while True:
                check_stop()
                sleep_until_due(BOT)
                check_stop()
                if not run_cycle():
                    logger.error("cykl nieudany — zatrzymuję bota")
                    request_stop()
                    break
                sleep_until_due(BOT, log=False)
                # Reset visited dopiero po CD cyklu — przerwany cykl można wznowić.
                manager.reset_all_hero_visited()
        except StopRequested:
            logger.warning("bot zatrzymany (gra pozostaje otwarta)")


def _on_ui_ready() -> None:
    """Discord + listener F9 + wątek bota (zatrzymany — czeka na Start z panelu WWW)."""
    start_discord_bot()
    start_hotkey_listener()
    threading.Thread(target=_bot_loop, name="bot", daemon=True).start()


if __name__ == "__main__":
    run_www(on_ready=_on_ui_ready, on_start=clear_stop, on_stop=request_stop)

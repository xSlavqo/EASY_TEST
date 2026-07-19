"""Punkt wejścia — uruchom grę, bot, zamknij grę."""

import random
import sys
import threading
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import activate_window, close_windows, run_game
from game import in_game
from game.hero_manager import manager
from log import logger
from state.keys import BOT, TASK_ALLIANCE_RSS
from state.schedule import is_due, schedule, sleep_until_due
from state.settings import settings
from state.stop import StopRequested, check_stop, sleep as stop_sleep, start_hotkey_listener
from tasks.alliance_rss import alliance_rss
from tasks.gather_rss import gather_rss
from ui.app import run_ui

_CYCLE_FAIL_RETRY_SEC = 60.0

_CYCLE_INTERVAL_MIN_SEC = 4 * 60 * 60
_CYCLE_INTERVAL_MAX_SEC = 5 * 60 * 60
_ALLIANCE_COOLDOWN_SEC = 18 * 60 * 60

# Odczekanie na przeładowanie konta po swapie, zanim aktywujemy okno gry.
_RELOGIN_FOCUS_DELAY_SEC = 15.0


def _run_cycle() -> bool:
    """Jeden cykl: uruchom grę → RSS na każdym bohaterze → zamknij grę."""
    if not run_game():
        return False

    while True:
        if not manager.current_hero():
            close_windows("game")
            return False

        if is_due(TASK_ALLIANCE_RSS):
            alliance_rss()

        rss = gather_rss()
        if not rss[0]:
            close_windows("game")
            return False
        logger.info("wysłano %s marszy", rss[1])

        manager.hero_visited()

        swapped = manager.swap_hero()
        if swapped is None:
            break
        if not swapped:
            close_windows("game")
            return False

        stop_sleep(_RELOGIN_FOCUS_DELAY_SEC)
        activate_window("game", attempts=8)

    logger.info("wysłaliśmy %s", ", ".join(manager.visited_ids))

    schedule(BOT, random.uniform(_CYCLE_INTERVAL_MIN_SEC, _CYCLE_INTERVAL_MAX_SEC))
    if is_due(TASK_ALLIANCE_RSS):
        schedule(TASK_ALLIANCE_RSS, _ALLIANCE_COOLDOWN_SEC)

    if settings.close_game_after_cycle:
        for sec in (30, 25, 20, 15, 10):
            logger.info("zamknięcie gry za %s s", sec)
            stop_sleep(5)
        for sec in range(5, 0, -1):
            logger.info("zamknięcie gry za %s s", sec)
            stop_sleep(1)
        if not close_windows("game"):
            logger.error("nie udało się zamknąć gry")
            return False

    return True


def _bot_loop() -> None:
    """Pętla bota — działa w tle, równolegle z UI."""
    try:
        while True:
            check_stop()
            sleep_until_due(BOT)
            check_stop()
            if _run_cycle():
                sleep_until_due(BOT, log=False)
                # Reset dopiero po przerwie 4-5 h — retry po błędzie pamięta visited.
                manager.reset_all_hero_visited()
            else:
                logger.error("cykl nieudany — ponowienie bez aktualizacji harmonogramu")
                stop_sleep(_CYCLE_FAIL_RETRY_SEC)
    except StopRequested:
        logger.warning("bot zatrzymany przez użytkownika (gra pozostaje otwarta)")


def _start_bot() -> None:
    """Start po gotowym UI — żeby pierwsze logi trafiły też do terminala."""
    start_hotkey_listener()
    threading.Thread(target=_bot_loop, name="bot", daemon=True).start()


if __name__ == "__main__":
    run_ui(on_ready=_start_bot)

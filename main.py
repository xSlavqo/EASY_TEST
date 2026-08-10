"""Punkt wejścia — uruchom grę, bot, zamknij grę."""

import random
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import activate_window, close_windows, run_game
from discord_bot import start_discord_bot
from game import in_game
from game.hero_manager import manager
from log import logger
from state.keys import BOT, TASK_ALLIANCE_RSS
from state.schedule import is_due, schedule, sleep_until_due
from state.settings import settings
from state.stop import (
    StopRequested,
    check_stop,
    clear_stop,
    is_stopped,
    request_stop,
    sleep as stop_sleep,
    start_hotkey_listener,
)
from tasks.alliance_pit import alliance_pit
from tasks.alliance_rss import alliance_rss
from tasks.gather_rss import gather_rss
from www.app import run_www

_CYCLE_FAIL_RETRY_SEC = 60.0

_CYCLE_INTERVAL_MIN_SEC = 4 * 60 * 60
_CYCLE_INTERVAL_MAX_SEC = 5 * 60 * 60
_ALLIANCE_COOLDOWN_SEC = 10 * 60 * 60

# Odczekanie na przeładowanie konta po swapie, zanim aktywujemy okno gry.
_RELOGIN_FOCUS_DELAY_SEC = 15.0


def _run_cycle() -> bool:
    """Jeden cykl: uruchom grę → RSS na każdym bohaterze → zamknij grę."""
    if not run_game():
        return False

    # Pit occupied/not_built → nie wołaj u kolejnych hero w cyklu.
    alliance_pit_skip = False

    while True:
        # Wykryj zalogowanego hero (main.png).
        if not manager.current_hero():
            request_stop()
            return False

        # Już visited (np. po restarcie po failu swapu) — pomiń taski, od razu swap.
        if not manager.is_visited():
            # Ally tylko gdy hero ma sojusz.
            if manager.is_in_alliance():
                # Zbieranie surowców sojuszu.
                if settings.alliance_rss_enabled and is_due(TASK_ALLIANCE_RSS):
                    activate_window("game", attempts=8)
                    alliance_rss()
                # Centrum zasobów przymierza (pit).
                if settings.alliance_pit_enabled and not alliance_pit_skip:
                    activate_window("game", attempts=8)
                    alliance_pit_skip = alliance_pit()

            # Zbieranie RSS na mapie — fail → koniec taska u tego hero, jedziemy dalej.
            if settings.gather_rss_enabled:
                activate_window("game", attempts=8)
                rss = gather_rss()
                if not rss[0]:
                    logger.error("gather_rss nieudany — przechodzę do kolejnego hero")

            # Oznacz hero jako odwiedzonego w tym cyklu.
            manager.hero_visited()

        # Swap na kolejnego hero / konto.
        swapped = manager.swap_hero()
        if swapped is None:
            # Brak hero na koncie → account_swap; 2× fail → wyłącz swap kont.
            swapped = manager.account_swap()
            if swapped is False:
                logger.warning("account_swap nieudany — wracam do gry i ponawiam raz")
                in_game()
                swapped = manager.account_swap()
                if swapped is False:
                    in_game()
                    manager.disable_account_swap()
                    swapped = None
            if swapped is None:
                break
        if not swapped:
            request_stop()
            return False

        # Po swapie — focus okna gry.
        stop_sleep(_RELOGIN_FOCUS_DELAY_SEC)
        activate_window("game", attempts=8)

    # Harmonogram kolejnego cyklu / cooldown ally RSS.
    schedule(BOT, random.uniform(_CYCLE_INTERVAL_MIN_SEC, _CYCLE_INTERVAL_MAX_SEC))
    if settings.alliance_rss_enabled and is_due(TASK_ALLIANCE_RSS):
        schedule(TASK_ALLIANCE_RSS, _ALLIANCE_COOLDOWN_SEC)

    # Opcjonalne zamknięcie gry po cyklu.
    if settings.close_game_after_cycle:
        logger.info("cykl OK — zamknięcie gry za 30 s")
        stop_sleep(30)
        if not close_windows("game"):
            logger.error("nie udało się zamknąć gry")
            return False

    return True


def _bot_loop() -> None:
    """Pętla bota — czeka na Start z UI, potem działa aż do Stop/F9."""
    while True:
        while is_stopped():
            time.sleep(0.1)
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


def _on_ui_ready() -> None:
    """Discord + listener F9 + wątek bota (zatrzymany — czeka na Start z panelu WWW)."""
    start_discord_bot()
    start_hotkey_listener()
    threading.Thread(target=_bot_loop, name="bot", daemon=True).start()


if __name__ == "__main__":
    run_www(on_ready=_on_ui_ready, on_start=clear_stop, on_stop=request_stop)

"""Jeden cykl bota: gra → taski u bohaterów → swap → harmonogram."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from client import close_windows, run_game
from game import in_game
from game.hero_manager import manager
from log import logger
from state.keys import BOT, TASK_ALLIANCE_PIT, TASK_ALLIANCE_RSS
from state.schedule import is_due, schedule
from state.settings import settings
from state.stop import sleep as stop_sleep
from tasks.alliance_pit import alliance_pit, is_wave_active, reset_cycle_state
from tasks.alliance_rss import alliance_rss
from tasks.gather_rss import gather_rss

_CYCLE_INTERVAL_MIN_SEC = 4 * 60 * 60
_CYCLE_INTERVAL_MAX_SEC = 5 * 60 * 60
_ALLIANCE_COOLDOWN_SEC = 10 * 60 * 60

# Odczekanie na przeładowanie konta po swapie (potem in_game + current_hero).
_RELOGIN_FOCUS_DELAY_SEC = 15.0

# Taski zakończone u bieżącego hero (True z taska). Reset po udanym swapie.
_done_tasks: set[str] = set()
# Ile razy w tej sesji hero restartowaliśmy grę po failu taska (max 1).
_task_fail_restarts = 0


def run_cycle() -> bool:
    """Jeden cykl: uruchom grę → RSS na każdym bohaterze → zamknij grę."""
    if not run_game():
        return False

    reset_cycle_state()
    _reset_hero_task_state()

    while True:
        if not _ensure_current_hero():
            return False

        # Już visited (np. po restarcie po failu swapu) — pomiń taski, od razu swap.
        if not manager.is_visited():
            rss = _run_task(
                "alliance_rss",
                alliance_rss,
                enabled=settings.alliance_rss_enabled,
                due=is_due(TASK_ALLIANCE_RSS),
                require_alliance=True,
            )
            if rss is False:
                if not _restart_after_task_fail():
                    return False
                continue

            # Każdy hero woła pit; gather/building/not_built/skip — wewnątrz taska.
            pit = _run_task(
                "alliance_pit",
                alliance_pit,
                enabled=settings.alliance_pit_enabled,
                due=is_due(TASK_ALLIANCE_PIT) or is_wave_active(),
                require_alliance=True,
            )
            if pit is False:
                if not _restart_after_task_fail():
                    return False
                continue

            gather = _run_task(
                "gather_rss",
                gather_rss,
                enabled=settings.gather_rss_enabled,
            )
            if gather is False:
                if not _restart_after_task_fail():
                    return False
                continue

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
            logger.error("swap_hero nieudany")
            return False

        # Udana zmiana postaci/konta → czyste flagi tasków u nowego hero.
        _reset_hero_task_state()

        # Po swapie — czekamy na przeładowanie; pętla wraca do in_game + current_hero.
        stop_sleep(_RELOGIN_FOCUS_DELAY_SEC)

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


def _run_task(
    name: str,
    fn: Callable[[], Any],
    *,
    enabled: bool | None = None,
    due: bool | None = None,
    require_alliance: bool | None = None,
) -> bool | None:
    """
    Odpal task albo pomiń.

    Kryteria (None = nie sprawdzaj): enabled, due, require_alliance.
    Już w _done_tasks → pomiń.
    True → flaga. False → retry (restart w cyklu). None → pominięty.
    """
    if name in _done_tasks:
        logger.info("task %s już wykonany — pomijam", name)
        return None

    if enabled is False:
        return None
    if due is False:
        return None
    if require_alliance is True and not manager.is_in_alliance():
        return None
    if require_alliance is False and manager.is_in_alliance():
        return None

    result = fn()
    # gather_rss → (ok, marches); reszta → bool
    ok = bool(result[0]) if isinstance(result, tuple) else bool(result)

    if ok:
        _done_tasks.add(name)
        logger.info("task %s OK — flaga ustawiona", name)
        return True

    logger.error("task %s nieudany", name)
    return False


def _reset_hero_task_state() -> None:
    """Wyczyść flagi tasków i licznik restartów (start cyklu / udany swap)."""
    global _task_fail_restarts
    _done_tasks.clear()
    _task_fail_restarts = 0


def _restart_after_task_fail() -> bool:
    """Jednorazowy restart gry po failu taska — flagi _done_tasks zostają."""
    global _task_fail_restarts
    if _task_fail_restarts >= 1:
        logger.error("task nieudany po restarcie gry — kończę cykl")
        return False

    _task_fail_restarts += 1
    logger.warning("task nieudany — zamykam grę i wznawiam (flagi tasków zostają)")
    if not close_windows("game"):
        logger.error("nie udało się zamknąć gry po failu taska")
        return False
    if not run_game():
        logger.error("nie udało się uruchomić gry po failu taska")
        return False
    return True


def _ensure_current_hero() -> bool:
    """
    in_game → wykryj zalogowanego hero (main.png).

    Przy failu: zamknij grę → uruchom od nowa → jedna dodatkowa próba.
    False → run_cycle kończy się failiem (main zatrzymuje bota).
    """
    if not in_game():
        logger.warning("in_game nieudany przed current_hero")
    elif manager.current_hero():
        return True

    logger.warning("current_hero nieudany — zamykam grę i próbuję raz od nowa")
    if not close_windows("game"):
        logger.error("nie udało się zamknąć gry po failu current_hero")
        return False
    if not run_game():
        logger.error("nie udało się uruchomić gry po failu current_hero")
        return False
    if not in_game():
        logger.error("in_game nieudany po restarcie gry")
        return False
    if manager.current_hero():
        return True

    logger.error("current_hero nieudany po restarcie gry")
    return False

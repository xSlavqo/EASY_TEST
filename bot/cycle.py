"""Jeden cykl bota: gra → taski u bohaterów → swap → harmonogram."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from client import activate_window, close_windows, run_game
from game import in_game
from game.hero_manager import manager
from log import logger
from state.keys import (
    BOT,
    TASK_ALLIANCE_PIT,
    TASK_ALLIANCE_RSS,
    scount_sentry_post_schedule_id,
)
from state.schedule import is_due, schedule
from state.settings import settings
from state.stop import sleep as stop_sleep
from tasks.alliance_pit import alliance_pit, is_wave_active, reset_cycle_state
from tasks.alliance_rss import alliance_rss
from tasks.gather_rss import gather_rss
from tasks.scount_sentry_post import scount_sentry_post

# Taski zakończone u bieżącego hero (True z taska). Reset po udanym swapie.
_done_tasks: set[str] = set()
# Ile razy w tej sesji hero restartowaliśmy grę po failu taska (max 1).
_task_fail_restarts = 0


def _hours_to_sec(hours: float) -> float:
    """Godziny z ustawień → sekundy do schedule()."""
    return max(0.0, float(hours)) * 3600.0


def _cycle_wait_sec() -> float:
    """Losowy czas do następnego cyklu (min–max z panelu, w sekundach)."""
    lo = _hours_to_sec(settings.cycle_interval_min_h)
    hi = _hours_to_sec(settings.cycle_interval_max_h)
    if hi < lo:
        lo, hi = hi, lo
    return random.uniform(lo, hi)


def run_cycle() -> bool:
    """Jeden cykl: uruchom grę → RSS na każdym bohaterze → zamknij grę."""
    if not run_game():
        logger.warning("run_cycle — run_game nieudany")
        return False

    reset_cycle_state()
    _reset_hero_task_state()

    while True:
        if not _ensure_current_hero():
            logger.warning("run_cycle — _ensure_current_hero nieudany")
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

            ssp_id = _ssp_schedule_id()
            ssp = _run_task(
                "scount_sentry_post",
                scount_sentry_post,
                enabled=settings.scount_sentry_post_enabled,
                due=ssp_id is not None and is_due(ssp_id),
            )
            if ssp is False:
                if not _restart_after_task_fail():
                    return False
                continue
            if ssp is True and ssp_id is not None:
                schedule(ssp_id, _hours_to_sec(settings.ssp_cooldown_h))

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

        # Po swapie — czekamy na przeładowanie, potem fokus; pętla → in_game + current_hero.
        stop_sleep(float(settings.relogin_focus_delay_sec))
        if not activate_window("game"):
            logger.warning("nie udało się aktywować okna gry po swapie")

    # Harmonogram kolejnego cyklu / cooldown ally RSS (wartości z panelu WWW).
    schedule(BOT, _cycle_wait_sec())
    if settings.alliance_rss_enabled and is_due(TASK_ALLIANCE_RSS):
        schedule(TASK_ALLIANCE_RSS, _hours_to_sec(settings.alliance_rss_cooldown_h))

    # Opcjonalne zamknięcie gry po cyklu.
    if settings.close_game_after_cycle:
        delay = float(settings.close_game_delay_sec)
        logger.info("cykl OK — zamknięcie gry za %.0f s", delay)
        stop_sleep(delay)
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


def _ssp_schedule_id() -> str | None:
    """Klucz harmonogramu SSP dla zalogowanego hero, albo None."""
    for hero in manager.heroes:
        if hero.logged_in:
            return scount_sentry_post_schedule_id(hero.email, hero.id)
    return None


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
    if not activate_window("game"):
        logger.warning("nie udało się aktywować okna gry przed current_hero")
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

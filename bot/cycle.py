"""Jeden cykl bota: gra → taski u bohaterów → swap → harmonogram."""

from __future__ import annotations

import random

from client import activate_window, close_windows, run_game
from game import in_game, is_in_game
from game.hero_manager import manager
from log import logger
from state.keys import BOT
from state.schedule import schedule
from state.settings import settings
from state.stop import sleep as stop_sleep
from tasks.alliance_pit import clear_expired_pit, reset_not_built_pit

from .task_manager import task_manager


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
    """Jeden cykl: clear pit/visited → gra → identify → taski → swap → harmonogram."""
    clear_expired_pit()
    reset_not_built_pit()
    manager.reset_all_hero_visited()

    if not run_game():
        logger.warning("run_cycle — run_game nieudany")
        return False

    while True:
        if not _ensure_current_hero():
            logger.warning("run_cycle — nie udało się ustalić current hero — stop")
            return False

        if _should_run_tasks():
            task_manager.run_tasks()
        manager.hero_visited()

        swapped = _swap_next_hero()
        if swapped is None:
            break
        if not swapped:
            return False

        stop_sleep(float(settings.relogin_focus_delay_sec))
        if not activate_window("game"):
            logger.warning("nie udało się aktywować okna gry po swapie")

    schedule(BOT, _cycle_wait_sec())

    if settings.close_game_after_cycle:
        delay = float(settings.close_game_delay_sec)
        stop_sleep(delay)
        if not close_windows("game"):
            logger.error("nie udało się zamknąć gry")
            return False

    return True


def _should_run_tasks() -> bool:
    """True = wołaj run_tasks. False = pomiń (mismatch / visited / wyłączony / brak tasków)."""
    if manager.consume_swap_mismatch():
        return False
    if manager.is_visited():
        return False
    if not manager.is_hero_enabled():
        return False
    if not task_manager.has_any_task_enabled():
        hero = manager.logged_in_hero()
        logger.info(
            "hero %s — wszystkie taski wyłączone, pomijam",
            hero.nick if hero is not None else "?",
        )
        return False
    return True


def _swap_next_hero() -> bool | None:
    """
    True — zamiana OK, kontynuuj pętlę.
    None — brak kolejnych hero / kont, koniec cyklu.
    False — błąd UI, stop bota.
    """
    swapped = manager.swap_hero()
    if swapped is True:
        return True
    if swapped is False:
        logger.error("swap_hero nieudany")
        return False

    # None — brak postaci na koncie → próba innego konta.
    swapped = manager.account_swap()
    if swapped is True:
        return True
    if swapped is None:
        return None

    logger.warning("account_swap nieudany — wracam do gry i ponawiam raz")
    in_game()
    swapped = manager.account_swap()
    if swapped is True:
        return True
    if swapped is False:
        in_game()
        manager.disable_account_swap()
        return None
    return None


def _ensure_current_hero() -> bool:
    """
    current_hero: True OK; False → stop; None → jeden swap, potem znowu current_hero.
    Nadal nie True → stop bota.
    """
    if not activate_window("game"):
        logger.warning("nie udało się aktywować okna gry przed current_hero")
    if not is_in_game():
        logger.warning("is_in_game nieudany przed current_hero")
        return False

    result = manager.current_hero()
    if result is True:
        return True
    if result is False:
        logger.error("current_hero False — stop")
        return False

    # None = unknown nick — jedna próba swapu.
    logger.warning("current_hero unknown — jedna próba swap_hero / account_swap")
    swapped = manager.swap_hero()
    if swapped is None:
        swapped = manager.account_swap()
    if swapped is not True:
        logger.error("swap po unknown nieudany — stop")
        return False

    stop_sleep(float(settings.relogin_focus_delay_sec))
    if not activate_window("game"):
        logger.warning("nie udało się aktywować okna gry po swapie (unknown)")
    if not is_in_game():
        logger.error("is_in_game nieudany po swapie z unknown")
        return False

    result = manager.current_hero()
    if result is True:
        return True
    logger.error("current_hero nadal nie True po jednym swapie — stop")
    return False

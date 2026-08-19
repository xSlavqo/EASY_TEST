"""Jeden cykl bota: gra → taski u bohaterów → swap → harmonogram."""

from __future__ import annotations

import random

from client import activate_window, close_windows, run_game
from game import in_game, is_in_game
from game.hero_manager import manager
from log import logger
from state.keys import BOT, TASK_ALLIANCE_RSS
from state.schedule import is_due, schedule
from state.settings import settings
from state.stop import sleep as stop_sleep
from tasks.alliance_pit import reset_cycle_state

from .task_manager import task_manager

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
    """Jeden cykl: uruchom grę → taski u bohaterów → swap → harmonogram."""
    global _task_fail_restarts

    if not run_game():
        logger.warning("run_cycle — run_game nieudany")
        return False

    reset_cycle_state()
    task_manager.reset_session()
    _task_fail_restarts = 0

    while True:
        if not _ensure_current_hero():
            logger.warning("run_cycle — _ensure_current_hero nieudany")
            return False

        # Swap na inny nick niż cel (OCR 1/l) — cel wyłączony, bez tasków, kolejny swap.
        skip_tasks = manager.consume_swap_mismatch()

        # Już visited (np. po restarcie po failu swapu) — pomiń taski, od razu swap.
        # Wyłączony w panelu: bez tasków, oznacz visited, idź do kolejnego.
        if not skip_tasks and not manager.is_visited():
            if not manager.is_hero_enabled():
                manager.hero_visited()
            elif not task_manager.has_any_task_enabled():
                hero = manager.logged_in_hero()
                logger.info(
                    "hero %s — wszystkie taski wyłączone, pomijam",
                    hero.nick if hero is not None else "?",
                )
                manager.hero_visited()
            else:
                if task_manager.run_on_current_hero() is False:
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

        # Udana zmiana postaci/konta → czysta sesja tasków u nowego hero.
        task_manager.reset_session()
        _task_fail_restarts = 0

        # Po swapie — czekamy na przeładowanie, potem fokus; pętla → is_in_game + current_hero.
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
        stop_sleep(delay)
        if not close_windows("game"):
            logger.error("nie udało się zamknąć gry")
            return False

    return True


def _restart_after_task_fail() -> bool:
    """Jednorazowy restart gry po failu taska — flagi _done w task_manager zostają."""
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
    is_in_game → current_hero.

    Obcy nick → swap_hero, potem account_swap (bez restartu gry).
    Pusty OCR / brak UI → jedna próba: zamknij grę i od nowa.
    """
    result = _identify_hero()
    if result is True:
        return True
    if result is None:
        return _recover_unknown_hero()

    logger.warning("current_hero nieudany — zamykam grę i próbuję raz od nowa")
    if not close_windows("game"):
        logger.error("nie udało się zamknąć gry po failu current_hero")
        return False
    if not run_game():
        logger.error("nie udało się uruchomić gry po failu current_hero")
        return False
    result = _identify_hero()
    if result is True:
        return True
    if result is None:
        return _recover_unknown_hero()

    logger.error("current_hero nieudany po restarcie gry")
    return False


def _identify_hero() -> bool | None:
    """Przegląd + OCR. True / None / False jak current_hero (albo False gdy nie w grze)."""
    if not activate_window("game"):
        logger.warning("nie udało się aktywować okna gry przed current_hero")
    if not is_in_game():
        logger.warning("is_in_game nieudany przed current_hero")
        return False
    return manager.current_hero()


def _recover_unknown_hero() -> bool:
    """Obcy nick: swap postaci, jak trzeba konto. UI złapane, a brak trafienia → błąd, bez powtórek."""
    swapped = manager.swap_hero()
    if swapped is True:
        return _identify_after_swap()
    if swapped is False:
        logger.error("swap_hero nieudany przy obcym nicku (UI / potwierdzenie)")
        return False

    acc = manager.account_swap()
    if acc is True:
        return _identify_after_swap()
    if acc is None:
        logger.error("obcy nick i brak włączonych nieodwiedzonych na liście")
        return False

    logger.error("account_swap nie znalazł konta (UI było, matching nie) — nie ponawiam")
    return False


def _identify_after_swap() -> bool:
    """Po udanym swapie: pauza, fokus, znowu current_hero. Nadal obcy → błąd bez pętli."""
    stop_sleep(float(settings.relogin_focus_delay_sec))
    if not activate_window("game"):
        logger.warning("nie udało się aktywować okna gry po swapie (obcy nick)")
    if not is_in_game():
        logger.error("is_in_game nieudany po swapie z obcego nicku")
        return False
    result = manager.current_hero()
    if result is True:
        return True
    if result is None:
        logger.error("po swapie nadal nick nie na liście — nie ponawiam")
        return False
    logger.error("po swapie current_hero nie odczytał nicku")
    return False

"""
Start i zamknięcie gry — launcher, przycisk Start, taskkill.

Fokus okna jest w client.window; run_game składa start + aktywację.
"""

from __future__ import annotations

import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import find_and_click
from log import logger
from state.stop import sleep as stop_sleep

from .window import (
    GAME_PROCESS,
    LAUNCHER_PROCESSES,
    _MAX_GAME_WINDOWS,
    _process_running,
    _window_hwnds,
    activate_window,
    game_window_rect,
)

LAUNCHER_PATH = Path(r"C:\Program Files (x86)\Call of Dragons\launcher.exe")
START_BUTTON_TEMPLATE = "game_start.png"

_PROCESS_WAIT_TIMEOUT = 90.0
_START_CLICK_TIMEOUT = 60.0
_GAME_LOADED_INITIAL_DELAY = 10.0
_CLOSE_TIMEOUT = 30.0
_CREATE_NO_WINDOW = 0x08000000

Target = Literal["game", "launcher", "all"]

# Publiczne nazwy zostają tu — wcześniej cały klient był w tym pliku.
__all__ = [
    "activate_window",
    "close_windows",
    "game_window_rect",
    "run_game",
    "start_game",
    "start_launcher",
]


def run_game() -> bool:
    """Uruchom grę i aktywuj okno. False gdy nie ma procesu albo nie ma fokusu."""
    if _process_running(GAME_PROCESS):
        if len(_window_hwnds(GAME_PROCESS)) >= _MAX_GAME_WINDOWS:
            logger.warning("za dużo okien gry — zamykam i startuję od nowa")
            close_windows("all")
        else:
            if not activate_window("game", attempts=8):
                logger.error("nie udało się aktywować okna gry")
                return False
            return True

    if not start_game():
        logger.warning("run_game — start_game nieudany")
        return False

    stop_sleep(_GAME_LOADED_INITIAL_DELAY)
    if not activate_window("game", attempts=8):
        logger.error("nie udało się aktywować okna gry po starcie")
        return False
    return True


def close_windows(target: Target = "all", *, timeout: float = _CLOSE_TIMEOUT) -> bool:
    """Zamknij procesy gry i/lub launchera (taskkill)."""
    names: list[str] = []
    if target in ("game", "all"):
        names.append(GAME_PROCESS)
    if target in ("launcher", "all"):
        names.extend(LAUNCHER_PROCESSES)

    running = [name for name in dict.fromkeys(names) if _process_running(name)]
    if not running:
        return True

    for name in running:
        subprocess.run(
            ["taskkill", "/IM", name, "/F"],
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
        )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(_process_running(name) for name in running):
            return True
        stop_sleep(random.uniform(0.3, 0.8))
    return False


def start_launcher() -> bool:
    """Zawsze odpal launcher.exe (nawet gdy już działa — wtedy okno samo wychodzi na wierzch)."""
    if not LAUNCHER_PATH.is_file():
        return False

    subprocess.Popen([str(LAUNCHER_PATH)], cwd=str(LAUNCHER_PATH.parent))

    deadline = time.monotonic() + _PROCESS_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if any(_process_running(name) for name in LAUNCHER_PROCESSES):
            return True
        stop_sleep(random.uniform(0.5, 1.2))
    return False


def start_game() -> bool:
    """Start launchera z pliku → Start → poczekaj na proces gry."""
    if not start_launcher():
        logger.error("nie mogę w żaden sposób włączyć launchera")
        return False

    stop_sleep(random.uniform(0.8, 1.6))

    if not find_and_click(START_BUTTON_TEMPLATE, timeout=_START_CLICK_TIMEOUT):
        logger.error("nie udało się kliknąć Start w launcherze")
        return False

    stop_sleep(random.uniform(1.0, 2.0))

    deadline = time.monotonic() + _PROCESS_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if _process_running(GAME_PROCESS):
            return True
        stop_sleep(random.uniform(0.5, 1.2))

    logger.error("proces gry nie pojawił się w czasie %s s po Start", _PROCESS_WAIT_TIMEOUT)
    return False


if __name__ == "__main__":
    print(f"run_game -> {run_game()}")

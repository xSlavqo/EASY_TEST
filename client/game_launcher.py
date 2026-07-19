"""
Moduł uruchamiania gry — 4 operacje: aktywuj, zamknij, start launchera, start gry.
"""

from __future__ import annotations

import ctypes
import random
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import find_and_click
from log import logger

LAUNCHER_PATH = Path(r"C:\Program Files (x86)\Call of Dragons\launcher.exe")
LAUNCHER_PROCESSES = ("Launcher_COD.exe", "launcher.exe")
GAME_PROCESS = "CallOfDragons.exe"
START_BUTTON_TEMPLATE = "game_start.png"

_PROCESS_WAIT_TIMEOUT = 90.0
_START_CLICK_TIMEOUT = 60.0
_GAME_LOADED_INITIAL_DELAY = 10.0
_MAX_GAME_WINDOWS = 2
_MIN_WINDOW_AREA = 50_000
_CLOSE_TIMEOUT = 30.0

_CREATE_NO_WINDOW = 0x08000000
_SW_RESTORE = 9

_user32 = ctypes.windll.user32

Target = Literal["game", "launcher", "all"]


def run_game() -> bool:
    """Uruchom grę (lub aktywuj działającą). False = nie udało się."""
    if _process_running(GAME_PROCESS):
        if len(_window_hwnds(GAME_PROCESS)) >= _MAX_GAME_WINDOWS:
            logger.warning("za dużo okien gry — zamykam i startuję od nowa")
            close_windows("all")
        else:
            activate_window("game", attempts=8)
            return True

    if not start_game():
        return False

    time.sleep(_GAME_LOADED_INITIAL_DELAY)
    activate_window("game", attempts=8)
    return True


def activate_window(target: Literal["game", "launcher"], *, attempts: int = 5) -> bool:
    """Aktywuj okno gry lub launchera (WinAPI po PID)."""
    processes = (GAME_PROCESS,) if target == "game" else LAUNCHER_PROCESSES
    for _ in range(attempts):
        for name in processes:
            for hwnd in _window_hwnds(name):
                if _focus_hwnd(hwnd):
                    return True
        time.sleep(random.uniform(0.25, 0.5))
    logger.warning("nie udało się aktywować okna: %s", target)
    return False


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
        time.sleep(random.uniform(0.3, 0.8))
    return False


def start_launcher() -> bool:
    """Uruchom launcher.exe i poczekaj aż proces się pojawi."""
    if not LAUNCHER_PATH.is_file():
        raise FileNotFoundError(f"Brak pliku: {LAUNCHER_PATH}")

    subprocess.Popen([str(LAUNCHER_PATH)], cwd=str(LAUNCHER_PATH.parent))

    deadline = time.monotonic() + _PROCESS_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if any(_process_running(name) for name in LAUNCHER_PROCESSES):
            return True
        time.sleep(random.uniform(0.5, 1.2))

    logger.error("launcher nie uruchomił się w czasie %s s", _PROCESS_WAIT_TIMEOUT)
    return False


def start_game() -> bool:
    """Aktywuj launcher → Start → poczekaj na proces gry."""
    if not activate_window("launcher"):
        logger.warning("launcher nieaktywny — uruchamiam z pliku")
        if not start_launcher():
            return False
        time.sleep(random.uniform(0.8, 1.6))
        if not activate_window("launcher"):
            logger.error("nie udało się aktywować launchera po uruchomieniu")
            return False

    time.sleep(random.uniform(0.8, 1.6))

    if not find_and_click(START_BUTTON_TEMPLATE, timeout=_START_CLICK_TIMEOUT):
        logger.error("nie udało się kliknąć Start w launcherze")
        return False

    time.sleep(random.uniform(1.0, 2.0))

    deadline = time.monotonic() + _PROCESS_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if _process_running(GAME_PROCESS):
            return True
        time.sleep(random.uniform(0.5, 1.2))

    logger.error("proces gry nie pojawił się w czasie %s s po Start", _PROCESS_WAIT_TIMEOUT)
    return False


# --- WinAPI / tasklist (wewnętrzne) ---


def _process_running(image_name: str) -> bool:
    return bool(_get_pids(image_name))


def _get_pids(image_name: str) -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    pids: list[int] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip() or "No tasks" in line:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            pids.append(int(parts[1].strip().strip('"')))
        except ValueError:
            continue
    return pids


def _window_hwnds(image_name: str) -> list[int]:
    pids = set(_get_pids(image_name))
    if not pids:
        return []

    candidates: list[tuple[int, int]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if not _user32.IsWindowVisible(hwnd) or _user32.GetParent(hwnd) != 0:
            return True
        pid_out = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value not in pids:
            return True
        rect = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        if area >= _MIN_WINDOW_AREA:
            candidates.append((hwnd, area))
        return True

    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback)
    _user32.EnumWindows(proc, 0)
    candidates.sort(key=lambda item: item[1], reverse=True)
    return [hwnd for hwnd, _ in candidates[:_MAX_GAME_WINDOWS]]


def _focus_hwnd(hwnd: int) -> bool:
    if not _user32.IsWindow(hwnd):
        return False
    if _user32.GetForegroundWindow() == hwnd:
        return True
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, _SW_RESTORE)
    _user32.ShowWindow(hwnd, _SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    return _user32.GetForegroundWindow() == hwnd


if __name__ == "__main__":
    print(f"run_game -> {run_game()}")

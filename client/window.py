"""
Odnajdź i aktywuj okno gry / launchera (WinAPI).
"""

from __future__ import annotations

import ctypes
import random
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from log import logger
from state.stop import sleep as stop_sleep

LAUNCHER_PROCESSES = ("Launcher_COD.exe", "launcher.exe")
GAME_PROCESS = "CallOfDragons.exe"

_MAX_GAME_WINDOWS = 2
_MIN_WINDOW_AREA = 50_000

_CREATE_NO_WINDOW = 0x08000000
_SW_RESTORE = 9
_SW_SHOW = 5
_VK_MENU = 0x12  # Alt
_KEYEVENTF_KEYUP = 0x0002
_ASFW_ANY = -1

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

# HWND na 64-bit musi iść jako wskaźnik, nie jako 32-bit int.
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_user32.AttachThreadInput.restype = wintypes.BOOL
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.IsIconic.restype = wintypes.BOOL
_user32.IsWindow.argtypes = [wintypes.HWND]
_user32.IsWindow.restype = wintypes.BOOL
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.ShowWindow.restype = wintypes.BOOL
_user32.BringWindowToTop.argtypes = [wintypes.HWND]
_user32.BringWindowToTop.restype = wintypes.BOOL


def activate_window(target: Literal["game", "launcher"], *, attempts: int = 5) -> bool:
    """Aktywuj okno gry lub launchera. True tylko gdy GetForegroundWindow = HWND."""
    processes = (GAME_PROCESS,) if target == "game" else LAUNCHER_PROCESSES
    for attempt in range(attempts):
        for name in processes:
            for hwnd in _window_hwnds(name):
                if _focus_hwnd(hwnd):
                    return True
        if attempt < attempts - 1:
            logger.warning(
                "activate_window(%s) — brak fokusu, próba %s/%s",
                target,
                attempt + 1,
                attempts,
            )
        stop_sleep(random.uniform(0.25, 0.5))
    logger.warning("nie udało się aktywować okna: %s", target)
    return False


def game_window_rect() -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) największego okna gry albo None."""
    hwnds = _window_hwnds(GAME_PROCESS)
    if not hwnds:
        return None
    rect = wintypes.RECT()
    if not _user32.GetWindowRect(hwnds[0], ctypes.byref(rect)):
        return None
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


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


def _window_tid_pid(hwnd: int) -> tuple[int, int]:
    """
    (thread_id, process_id) okna.

    GetWindowThreadProcessId: wartość zwrotna = wątek, DWORD pod wskaźnikiem = proces.
    """
    pid = wintypes.DWORD(0)
    tid = int(_user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))
    return tid, int(pid.value)


def _is_foreground(hwnd: int) -> bool:
    """True gdy fokus ma to okno albo inne okno tego samego procesu (np. pop-up)."""
    fg = _user32.GetForegroundWindow()
    if not fg:
        return False
    if int(fg) == int(hwnd):
        return True
    _, pid_fg = _window_tid_pid(int(fg))
    _, pid_target = _window_tid_pid(hwnd)
    return bool(pid_fg) and pid_fg == pid_target


def _tap_alt() -> None:
    """Krótki Alt — Windows częściej pozwala potem na SetForegroundWindow."""
    _user32.keybd_event(_VK_MENU, 0, 0, 0)
    _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)


def _focus_hwnd(hwnd: int) -> bool:
    """Przywróć okno WinAPI: Show → SetForeground → Alt → AttachThreadInput. Bez myszy."""
    if not _user32.IsWindow(hwnd):
        logger.warning("_focus_hwnd — IsWindow=False hwnd=%s", hwnd)
        return False
    if _is_foreground(hwnd):
        return True

    # Restore tylko gdy zminimalizowane — na fullscreenie psuje tryb okna.
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, _SW_RESTORE)
    else:
        _user32.ShowWindow(hwnd, _SW_SHOW)
    _user32.AllowSetForegroundWindow(_ASFW_ANY)

    _user32.SetForegroundWindow(hwnd)
    if _is_foreground(hwnd):
        return True

    # Alt = „input użytkownika”; po nim Windows chętniej oddaje focus.
    _tap_alt()
    _user32.SetForegroundWindow(hwnd)
    if _is_foreground(hwnd):
        return True

    # Windows blokuje „kradzież” fokusu — łączenie kolejek inputu (OK przy fullscreen).
    _steal_focus(hwnd)
    if _is_foreground(hwnd):
        return True

    _user32.SwitchToThisWindow(hwnd, True)
    ok = _is_foreground(hwnd)
    if not ok:
        logger.warning("_focus_hwnd — wszystkie metody fokusu padły hwnd=%s", hwnd)
    return ok


def _steal_focus(hwnd: int) -> None:
    """Dołącz wątek bota do wątku okna z fokusem i okna gry, potem SetForegroundWindow."""
    fg = _user32.GetForegroundWindow()
    cur_tid = int(_kernel32.GetCurrentThreadId())

    fg_tid = 0
    if fg:
        fg_tid, _ = _window_tid_pid(int(fg))
    target_tid, _ = _window_tid_pid(hwnd)

    attached_fg = False
    attached_target = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(_user32.AttachThreadInput(cur_tid, fg_tid, True))
        if target_tid and target_tid != cur_tid:
            attached_target = bool(_user32.AttachThreadInput(cur_tid, target_tid, True))
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
    finally:
        if attached_target:
            _user32.AttachThreadInput(cur_tid, target_tid, False)
        if attached_fg:
            _user32.AttachThreadInput(cur_tid, fg_tid, False)

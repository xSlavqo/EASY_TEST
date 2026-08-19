"""Zatrzymanie bota — skrót F9 / przycisk Stop. Start tylko z UI."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes

from log import logger

# Domyślnie zatrzymany — bot nie rusza, dopóki UI nie wywoła clear_stop().
_stop = threading.Event()
_stop.set()
_listener_started = False

HOTKEY_ID = 1
MOD_NOREPEAT = 0x4000
VK_F9 = 0x78
WM_HOTKEY = 0x0312


class StopRequested(Exception):
    """Użytkownik żąda natychmiastowego zatrzymania bota."""


def request_stop() -> None:
    if not _stop.is_set():
        _stop.set()
        logger.warning("zatrzymanie bota — przerywam natychmiast")


def clear_stop() -> None:
    if _stop.is_set():
        _stop.clear()
        logger.info("bot uruchomiony")


def is_stopped() -> bool:
    return _stop.is_set()


def check_stop() -> None:
    if _stop.is_set():
        raise StopRequested


def sleep(seconds: float, *, chunk: float = 0.05) -> None:
    """Przerywalny sleep — rzuca StopRequested po żądaniu stopu."""
    if seconds <= 0:
        check_stop()
        return

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        check_stop()
        remaining = deadline - time.monotonic()
        time.sleep(min(chunk, max(0.0, remaining)))


def _hotkey_listener() -> None:
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_F9):
        logger.error("nie udało się zarejestrować skrótu F9")
        return

    try:
        msg = wintypes.MSG()
        while True:
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) == 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                request_stop()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)


def start_hotkey_listener() -> None:
    global _listener_started
    if _listener_started:
        return
    _listener_started = True

    if sys.platform != "win32":
        logger.warning("skrót F9 dostępny tylko na Windows")
        return

    threading.Thread(target=_hotkey_listener, name="stop-hotkey", daemon=True).start()

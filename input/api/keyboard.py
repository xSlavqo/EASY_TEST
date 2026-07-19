"""
Moduł klawiatury — wpisywanie tekstu i pojedyncze klawisze (SendInput).
"""

from __future__ import annotations

import ctypes
import random
import time
from ctypes import wintypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

_user32 = ctypes.windll.user32

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

# Mapowanie nazw klawiszy na kody wirtualne (VK)
_VK: dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def press_key(key: str) -> None:
    """Naciśnij i puść pojedynczy klawisz (np. enter, tab, esc)."""
    vk = _resolve_vk(key)
    time.sleep(max(0.03, random.gauss(0.08, 0.02)))
    _send_vk(vk, key_up=False)
    time.sleep(random.uniform(0.04, 0.12))
    _send_vk(vk, key_up=True)


def type_text(text: str) -> None:
    """Wpisz tekst z losowymi opóźnieniami między znakami."""
    if not text:
        return

    time.sleep(max(0.05, random.gauss(0.15, 0.04)))

    for i, char in enumerate(text):
        _type_char(char)
        if i < len(text) - 1:
            time.sleep(max(0.05, random.gauss(0.12, 0.03)))


# ---------------------------------------------------------------------------
# WinAPI
# ---------------------------------------------------------------------------

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT)]


def _resolve_vk(key: str) -> int:
    """Rozwiąż nazwę klawisza na kod VK."""
    name = key.strip().lower()
    if name in _VK:
        return _VK[name]
    if len(key) == 1:
        vk = _user32.VkKeyScanW(ord(key))
        if vk == -1:
            raise ValueError(f"Nieobsługiwany znak: {key!r}")
        return vk & 0xFF
    raise ValueError(f"Nieznany klawisz: {key!r}")


def _send_input(inp: INPUT) -> None:
    if _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise OSError("SendInput nie powiódł się")


def _send_vk(vk: int, *, key_up: bool) -> None:
    """Wyślij zdarzenie klawisza po kodzie VK."""
    flags = KEYEVENTF_KEYUP if key_up else 0
    scan = _user32.MapVirtualKeyW(vk, 0)
    inp = INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0),
    )
    _send_input(inp)


def _type_char(char: str) -> None:
    """Wpisz jeden znak (Unicode — działa też z polskimi literami)."""
    code = ord(char)
    inp_down = INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0),
    )
    inp_up = INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(
            wVk=0,
            wScan=code,
            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=0,
        ),
    )
    _send_input(inp_down)
    time.sleep(random.uniform(0.03, 0.09))
    _send_input(inp_up)


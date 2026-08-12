"""
Moduł myszy — ruch kursora i kliknięcia (humanizowany input, SendInput).
"""

from __future__ import annotations

import ctypes
import math
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

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT)]


def click_at(x: int, y: int) -> None:
    """Przesuń kursor na (x, y) i kliknij lewym przyciskiem."""
    move_to(x, y)
    time.sleep(max(0.05, random.gauss(0.15, 0.04)))
    _send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(random.uniform(0.05, 0.12))
    _send_mouse(MOUSEEVENTF_LEFTUP)


def right_click_at(x: int, y: int) -> None:
    """Przesuń kursor na (x, y) i kliknij prawym przyciskiem."""
    move_to(x, y)
    time.sleep(max(0.05, random.gauss(0.15, 0.04)))
    _send_mouse(MOUSEEVENTF_RIGHTDOWN)
    time.sleep(random.uniform(0.05, 0.12))
    _send_mouse(MOUSEEVENTF_RIGHTUP)


def move_to(target_x: int, target_y: int) -> None:
    """Porusz kursor na cel po krzywej Béziera."""
    sx, sy = _cursor_pos()
    start = (float(sx), float(sy))
    end = (float(target_x), float(target_y))
    distance = math.hypot(end[0] - start[0], end[1] - start[1])

    if distance < 8:
        _move_short_path(start, end)
        return

    path = _build_path(start, end, overshoot=random.random() < 0.12)
    duration = max(0.2, random.gauss(0.15 + distance / 1500, 0.02))
    step_delay = duration / max(len(path) - 1, 1)

    for point in path[1:]:
        cx, cy = _cursor_pos()
        dx = int(round(point[0] - cx))
        dy = int(round(point[1] - cy))
        _move_relative(dx, dy)
        time.sleep(step_delay * random.uniform(0.85, 1.15))

    for _ in range(6):
        cx, cy = _cursor_pos()
        dx, dy = target_x - cx, target_y - cy
        if abs(dx) <= 1 and abs(dy) <= 1:
            break
        _move_relative(int(round(dx * 0.5)), int(round(dy * 0.5)))
        time.sleep(random.uniform(0.01, 0.02))


def _move_short_path(start: tuple[float, float], end: tuple[float, float]) -> None:
    """Krótki łuk — nawet gdy cel jest tuż pod kursorem (sąsiednie kliknięcia UI)."""
    spread = max(4.0, random.uniform(4, 10))
    mid = (
        (start[0] + end[0]) / 2 + random.uniform(-spread, spread),
        (start[1] + end[1]) / 2 + random.uniform(-spread, spread),
    )
    steps = random.randint(6, 12)
    for i in range(1, steps + 1):
        t = _ease_in_out(i / steps)
        u = 1.0 - t
        x = u * u * start[0] + 2 * u * t * mid[0] + t * t * end[0]
        y = u * u * start[1] + 2 * u * t * mid[1] + t * t * end[1]
        cx, cy = _cursor_pos()
        _move_relative(int(round(x - cx)), int(round(y - cy)))
        time.sleep(random.uniform(0.015, 0.035))

    for _ in range(4):
        cx, cy = _cursor_pos()
        dx, dy = int(round(end[0])) - cx, int(round(end[1])) - cy
        if abs(dx) <= 1 and abs(dy) <= 1:
            break
        _move_relative(int(round(dx * 0.5)), int(round(dy * 0.5)))
        time.sleep(random.uniform(0.01, 0.02))


def _build_path(start, end, *, overshoot: bool) -> list[tuple[float, float]]:
    """Ścieżka ruchu myszy z opcjonalnym overshoot."""
    c1, c2 = _random_control_points(start, end)
    steps = max(20, int(math.hypot(end[0] - start[0], end[1] - start[1]) / 8))
    points = []

    for i in range(steps + 1):
        t = _ease_in_out(i / steps)
        x, y = _bezier_point(t, start, c1, c2, end)
        if i == steps:
            points.append((x, y))
        else:
            points.append((x + random.uniform(-2, 2), y + random.uniform(-2, 2)))

    if overshoot:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy) or 1.0
        over = (
            end[0] + dx / length * random.uniform(4, 12),
            end[1] + dy / length * random.uniform(4, 12),
        )
        points.extend([over, end])

    return points


def _random_control_points(start, end):
    """Losowe punkty kontrolne krzywej Béziera."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    spread = math.hypot(dx, dy) * random.uniform(0.2, 0.45) or 1.0
    c1 = (
        start[0] + dx * random.uniform(0.15, 0.4) + random.uniform(-spread, spread),
        start[1] + dy * random.uniform(0.15, 0.4) + random.uniform(-spread, spread),
    )
    c2 = (
        start[0] + dx * random.uniform(0.6, 0.85) + random.uniform(-spread, spread),
        start[1] + dy * random.uniform(0.6, 0.85) + random.uniform(-spread, spread),
    )
    return c1, c2


def _bezier_point(t: float, p0, p1, p2, p3) -> tuple[float, float]:
    """Punkt na krzywej Béziera dla parametru t."""
    u = 1.0 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def _ease_in_out(t: float) -> float:
    """Wygładzenie prędkości (ease-in-out)."""
    return t * t * (3.0 - 2.0 * t)


def _send_mouse(flags: int, dx: int = 0, dy: int = 0) -> None:
    """Wyślij zdarzenie myszy przez SendInput."""
    inp = INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0),
    )
    if _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise OSError("SendInput nie powiódł się")


def _move_relative(dx: int, dy: int) -> None:
    """Przesuń kursor względnie o (dx, dy)."""
    if dx or dy:
        _send_mouse(MOUSEEVENTF_MOVE, dx, dy)


def _cursor_pos() -> tuple[int, int]:
    """Aktualna pozycja kursora na ekranie."""
    point = wintypes.POINT()
    if not _user32.GetCursorPos(ctypes.byref(point)):
        raise OSError("GetCursorPos nie powiódł się")
    return point.x, point.y

"""Klikanie w punkt lub region (warstwa nad input.engine.mouse)."""

from __future__ import annotations

import random

from ..engine.mouse import click_at

_DEFAULT_MARGIN = 0.15


def click_point(x: int, y: int) -> None:
    """Kliknij w punkt (x, y)."""
    click_at(int(x), int(y))


def click_region(
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    margin: float = _DEFAULT_MARGIN,
    offset_x: int = 0,
    offset_y: int = 0,
) -> None:
    """
    Kliknij losowo w region (x, y, w, h) — punkt z marginesem od obrysu.

    offset_x/offset_y przesuwają wyliczony punkt (np. klik obok znalezionego obrazu).
    """
    x, y, width, height = int(x), int(y), int(width), int(height)
    mx, my = int(width * margin), int(height * margin)
    left, top = x + mx, y + my
    right, bottom = x + width - mx, y + height - my
    if left >= right:
        left, right = x, x + width
    if top >= bottom:
        top, bottom = y, y + height

    px = random.randint(left, right) + int(offset_x)
    py = random.randint(top, bottom) + int(offset_y)
    click_at(px, py)

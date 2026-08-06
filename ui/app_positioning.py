"""Pozycjonowanie okna aplikacji względem monitorów i gry."""

from __future__ import annotations

import mss

from client import game_window_rect

_UI_W = 600
_UI_H = 800


def app_geometry(width: int = _UI_W, height: int = _UI_H) -> str:
    """Geometry tkintera: inny monitor niż gra, inaczej boczny, inaczej primary."""
    with mss.MSS() as sct:
        monitors = list(sct.monitors[1:])

    target = monitors[0] if monitors else None
    game = game_window_rect()
    if game is not None and len(monitors) > 1:
        gx = (game[0] + game[2]) // 2
        gy = (game[1] + game[3]) // 2
        others = [
            m
            for m in monitors
            if not (
                m["left"] <= gx < m["left"] + m["width"]
                and m["top"] <= gy < m["top"] + m["height"]
            )
        ]
        if others:
            target = max(
                others,
                key=lambda m: abs((m["left"] + m["width"] // 2) - gx),
            )
    elif len(monitors) > 1:
        target = monitors[1]  # boczny (nie primary)

    if target is None:
        return f"{width}x{height}"

    x = target["left"] + (target["width"] - width) // 2
    y = target["top"] + (target["height"] - height) // 2
    return f"{width}x{height}+{x}+{y}"

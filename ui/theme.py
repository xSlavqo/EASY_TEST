"""Wspólny ciemny motyw UI — domyślne style widgetów, nadpisywane przez **kw."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk

# Kolory motywu — zmiana tu = zmiana w całym UI
BG = "#2d2d2d"
FG = "#f0f0f0"
PANEL = "#383838"
SCROLL = "#555555"
CHECK_FG = "#1a1a1a"  # ptaszek (musi być ciemny na jasnym środku)
CHECK_SELECT = "#ffffff"


def apply_window(root: tk.Tk) -> None:
    """Tło okna + ciemny pasek tytułu Windows + styl scrollbara ttk."""
    root.configure(bg=BG)

    if sys.platform == "win32":
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=SCROLL,
        troughcolor=PANEL,
        bordercolor=PANEL,
        arrowcolor=FG,
        darkcolor=PANEL,
        lightcolor=PANEL,
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", "#666666"), ("pressed", "#777777")],
    )


def frame(parent: tk.Misc, **kw: object) -> tk.Frame:
    opts: dict = {"bg": BG}
    opts.update(kw)
    return tk.Frame(parent, **opts)


def label(parent: tk.Misc, **kw: object) -> tk.Label:
    opts: dict = {"bg": BG, "fg": FG}
    opts.update(kw)
    return tk.Label(parent, **opts)


def checkbutton(
    parent: tk.Misc,
    *,
    text: str,
    variable: tk.Variable,
    command: object = None,
    **kw: object,
) -> tk.Frame:
    """Checkbox z etykietą — zwraca wiersz (Frame) do pack/grid; **kw → Checkbutton."""
    row = frame(parent)
    opts: dict = {
        "bg": BG,
        "fg": CHECK_FG,
        "activebackground": BG,
        "activeforeground": CHECK_FG,
        "selectcolor": CHECK_SELECT,
        "highlightthickness": 0,
        "variable": variable,
        "command": command,
    }
    opts.update(kw)
    tk.Checkbutton(row, **opts).pack(side=tk.LEFT)
    label(row, text=text).pack(side=tk.LEFT)
    return row


def entry(parent: tk.Misc, **kw: object) -> tk.Entry:
    opts: dict = {
        "bg": PANEL,
        "fg": FG,
        "insertbackground": FG,
        "relief": tk.FLAT,
        "highlightthickness": 1,
        "highlightbackground": SCROLL,
        "highlightcolor": FG,
    }
    opts.update(kw)
    return tk.Entry(parent, **opts)


def button(parent: tk.Misc, **kw: object) -> tk.Button:
    opts: dict = {
        "bg": PANEL,
        "fg": FG,
        "activebackground": SCROLL,
        "activeforeground": FG,
        "relief": tk.FLAT,
        "highlightthickness": 0,
        "padx": 10,
        "pady": 4,
    }
    opts.update(kw)
    return tk.Button(parent, **opts)


def text(parent: tk.Misc, **kw: object) -> tk.Text:
    opts: dict = {
        "bg": PANEL,
        "fg": FG,
        "insertbackground": FG,
        "highlightthickness": 0,
        "borderwidth": 0,
        "wrap": tk.WORD,
        "font": ("Consolas", 9),
        "padx": 6,
        "pady": 6,
    }
    opts.update(kw)
    return tk.Text(parent, **opts)


def scrollbar(parent: tk.Misc, **kw: object) -> ttk.Scrollbar:
    opts: dict = {"orient": tk.VERTICAL, "style": "Dark.Vertical.TScrollbar"}
    opts.update(kw)
    return ttk.Scrollbar(parent, **opts)

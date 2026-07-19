"""Proste okno ustawień + terminal z logami bota."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
import tkinter as tk

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from log import logger
from state.settings import settings
from ui import theme


def run_ui(on_ready: Callable[[], None] | None = None) -> None:
    """Okno z checkboxem close_game_after_cycle i terminalem logów (połowa wysokości).

    on_ready — wywołane po podpięciu terminala do loggera (np. start bota).
    """
    root = tk.Tk()
    root.title("ustawienia")
    root.geometry("600x800")
    root.resizable(False, False)
    theme.apply_window(root)

    var = tk.BooleanVar(value=bool(settings.close_game_after_cycle))

    def on_toggle() -> None:
        settings.close_game_after_cycle = bool(var.get())

    # Górna połowa — ustawienia
    top = theme.frame(root, padx=16, pady=16, height=400)
    top.pack(side=tk.TOP, fill=tk.BOTH)
    top.pack_propagate(False)

    theme.checkbutton(
        top,
        text="Zamykaj grę po cyklu",
        variable=var,
        command=on_toggle,
    ).pack(anchor="w")

    # Dolna połowa — terminal logów
    bottom = theme.frame(root, height=400)
    bottom.pack(side=tk.BOTTOM, fill=tk.BOTH)
    bottom.pack_propagate(False)

    term_wrap = theme.frame(bottom)
    term_wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    terminal = theme.text(term_wrap, state=tk.DISABLED)
    scroll = theme.scrollbar(term_wrap, command=terminal.yview)
    terminal.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    terminal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    class _UiLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            msg = self.format(record) + "\n"
            root.after(0, _append_log, msg)

    def _append_log(msg: str) -> None:
        terminal.configure(state=tk.NORMAL)
        terminal.insert(tk.END, msg)
        terminal.see(tk.END)
        terminal.configure(state=tk.DISABLED)

    logger.attach_handler(_UiLogHandler())
    if on_ready is not None:
        root.after(0, on_ready)
    root.mainloop()


if __name__ == "__main__":
    run_ui()

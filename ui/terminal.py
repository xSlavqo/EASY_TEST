"""Terminal logów UI — widok + podpięcie loggera."""

from __future__ import annotations

import logging
import tkinter as tk

from log import logger
from ui import theme


def mount_terminal(root: tk.Tk) -> None:
    """Złóż panel terminala pod resztą UI i podłącz logi bota."""
    # Dolna strefa — zajmuje resztę okna.
    panel = theme.frame(root)
    panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Wrap z marginesem wokół Text + Scrollbar.
    wrap = theme.frame(panel)
    wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # Pole Text (tylko odczyt) + pionowy scroll po prawej.
    terminal = theme.text(wrap, state=tk.DISABLED)
    scroll = theme.scrollbar(wrap, command=terminal.yview)
    terminal.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    terminal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def append(msg: str) -> None:
        terminal.configure(state=tk.NORMAL)
        terminal.insert(tk.END, msg)
        terminal.see(tk.END)
        terminal.configure(state=tk.DISABLED)

    class _UiLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            root.after(0, append, self.format(record) + "\n")

    logger.attach_handler(_UiLogHandler())

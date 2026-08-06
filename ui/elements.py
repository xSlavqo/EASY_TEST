"""Elementy UI — każdy ma opis oraz indywidualne opcje (pack, styl, tekst).

theme = wspólny wygląd; tu = konkretne rozmieszczenie i „rzeczy” danego widgetu.
"""

from __future__ import annotations

import tkinter as tk

from ui import theme
from ui.app_positioning import app_geometry


# ── Okno główne ─────────────────────────────────────────────────────────────
# Główne okno ustawień bota (rozmiar/pozycja z app_positioning).

def root_window() -> tk.Tk:
    """Główne okno aplikacji — tytuł, geometria, motyw."""
    root = tk.Tk()
    root.title("ustawienia")
    root.geometry(app_geometry())
    root.resizable(False, False)
    theme.apply_window(root)
    return root


# ── Panel ustawień ───────────────────────────────────────────────────────────
# Górny box: opcje bota (checkboxy). Stała wysokość, nie kurczy się.

def settings_panel(parent: tk.Misc) -> tk.Frame:
    """Górny box ustawień."""
    fr = theme.frame(parent, padx=16, pady=16, height=400)
    fr.pack(side=tk.TOP, fill=tk.BOTH)
    fr.pack_propagate(False)
    return fr


# ── Checkbox ustawienia ──────────────────────────────────────────────────────

def setting_check(
    parent: tk.Misc,
    *,
    text: str,
    variable: tk.Variable,
    command: object = None,
) -> tk.Frame:
    """Checkbox zapisujący ustawienie (settings.*)."""
    row = theme.checkbutton(
        parent,
        text=text,
        variable=variable,
        command=command,
    )
    row.pack(anchor="w")
    return row


# ── Pasek przycisku Start/Stop ───────────────────────────────────────────────
# Wąski pasek nad terminalem; odliczanie + przycisk wyśrodkowane.

def bot_button_bar(parent: tk.Misc) -> tk.Frame:
    """Pasek pod ustawieniami — kontener na odliczanie i Start/Stop."""
    fr = theme.frame(parent, padx=16, pady=12)
    fr.pack(side=tk.TOP, fill=tk.X)
    return fr


# ── Odliczanie do następnego cyklu ───────────────────────────────────────────
# Nad Start/Stop. Opis + wartość; format zależny od pozostałego czasu.

def format_countdown(remaining: float | None) -> str:
    """>=1h → h+min; <1h → min; <10min → min+s; <1min → s."""
    if remaining is None:
        return "—"
    if remaining <= 0:
        return "w trakcie"
    total = int(remaining)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours >= 1:
        return f"{hours} h {minutes} min"
    if minutes >= 10:
        return f"{minutes} min"
    if minutes >= 1:
        return f"{minutes} min {seconds} s"
    return f"{seconds} s"


def cycle_countdown(parent: tk.Misc) -> tuple[tk.Label, tk.Frame]:
    """Wiersz: opis + odliczanie; zwraca (Label wartości, Frame wiersza)."""
    row = theme.frame(parent)
    row.pack(anchor="center", pady=(0, 8))
    theme.label(row, text="czas do następnego cyklu:", font=("Segoe UI", 10)).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    value = theme.label(row, text="—", font=("Segoe UI", 11, "bold"))
    value.pack(side=tk.LEFT)
    return value, row


def cycle_reset_button(
    parent: tk.Misc,
    *,
    command: object,
    text: str = "Reset",
) -> tk.Button:
    """Mały przycisk — reset odliczania / czyszczenie visited."""
    btn = theme.button(
        parent,
        text=text,
        command=command,
        font=("Segoe UI", 9),
        padx=10,
        pady=2,
    )
    btn.pack(side=tk.LEFT, padx=(10, 0))
    return btn


# ── Odwiedzeni hero w cyklu ──────────────────────────────────────────────────
# Lista z info.json (heroes.visited); Wyczyść = reset RAM + plik.

def visited_row(parent: tk.Misc) -> tuple[tk.Label, tk.Frame]:
    """Wiersz: liczba odwiedzonych hero; zwraca (Label wartości, Frame wiersza)."""
    row = theme.frame(parent)
    row.pack(anchor="center", pady=(0, 8))
    theme.label(row, text="odwiedzeni hero:", font=("Segoe UI", 10)).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    value = theme.label(row, text="0", font=("Segoe UI", 11, "bold"))
    value.pack(side=tk.LEFT)
    return value, row


# ── Odliczanie / stan pitu przymierza ────────────────────────────────────────
# Pod odliczaniem cyklu. Czas do następnego sprawdzenia + ostatni stan z OCR.

_PIT_STATUS_LABELS = {
    "not_built": "nie wybudowane",
    "building": "budowanie",
    "gather": "zbieranie",
    "occupied": "zajęte",
}


def format_pit_status(status: str | None) -> str:
    """not_built / building / gather / occupied → polska etykieta; brak → —."""
    if not status:
        return "—"
    return _PIT_STATUS_LABELS.get(status, status)


def pit_countdown(parent: tk.Misc) -> tuple[tk.Label, tk.Label, tk.Frame]:
    """Wiersz: czas do pitu + stan; zwraca (Label czasu, Label stanu, Frame wiersza)."""
    row = theme.frame(parent)
    row.pack(anchor="center", pady=(0, 8))
    theme.label(row, text="czas do pitu:", font=("Segoe UI", 10)).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    time_value = theme.label(row, text="—", font=("Segoe UI", 11, "bold"))
    time_value.pack(side=tk.LEFT)
    theme.label(row, text="stan:", font=("Segoe UI", 10)).pack(
        side=tk.LEFT, padx=(16, 8)
    )
    status_value = theme.label(row, text="—", font=("Segoe UI", 11, "bold"))
    status_value.pack(side=tk.LEFT)
    return time_value, status_value, row


# ── Przycisk Start / Stop (F9) ───────────────────────────────────────────────
# Duży przycisk sterowania botem. Start tylko stąd; Stop też przez F9.

def bot_button(parent: tk.Misc, *, command: object) -> tk.Button:
    """Przycisk Start/Stop bota (etykieta Start na start)."""
    btn = theme.button(
        parent,
        text="Start",
        command=command,
        font=("Segoe UI", 12, "bold"),
        padx=28,
        pady=10,
        width=14,
    )
    btn.pack(anchor="center")
    return btn

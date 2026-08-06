"""Sklejanie UI — elementy + callbacki; terminal w ui.terminal."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
import tkinter as tk

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game.hero_manager import manager
from log import logger
from state.keys import ALLIANCE_PIT_STATUS, BOT, TASK_ALLIANCE_PIT
from state.schedule import remaining_sec, schedule
from state.settings import settings
from state.stop import is_stopped
from state.store import INFO_PATH, get_data
from ui import elements as el
from ui.terminal import mount_terminal


def run_ui(
    on_ready: Callable[[], None] | None = None,
    on_start: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
) -> None:
    """Złóż okno: ustawienia, Start/Stop, odliczanie, terminal."""
    root = el.root_window()

    settings_box = el.settings_panel(root)

    # (klucz w config.json, etykieta UI)
    _CHECKS = (
        ("close_game_after_cycle", "Zamykaj grę po cyklu"),
        ("alliance_rss_enabled", "Odbierz surowce sojuszu"),
        ("alliance_pit_enabled", "Centrum zasobów przymierza"),
        ("gather_rss_enabled", "Zbieranie RSS"),
    )
    for key, label in _CHECKS:
        var = tk.BooleanVar(value=bool(getattr(settings, key)))

        def _on_toggle(k: str = key, v: tk.BooleanVar = var) -> None:
            setattr(settings, k, bool(v.get()))

        el.setting_check(settings_box, text=label, variable=var, command=_on_toggle)

    btn_bar = el.bot_button_bar(root)
    countdown, countdown_row = el.cycle_countdown(btn_bar)

    def on_reset_cycle() -> None:
        # 0 s → next_run_at = teraz → sleep_until_due wychodzi, cykl leci od razu
        schedule(BOT, 0)

    el.cycle_reset_button(countdown_row, command=on_reset_cycle)

    pit_time, pit_status, pit_row = el.pit_countdown(btn_bar)

    def on_reset_pit() -> None:
        schedule(TASK_ALLIANCE_PIT, 0)

    el.cycle_reset_button(pit_row, command=on_reset_pit)

    visited_count, visited_row = el.visited_row(btn_bar)

    def on_clear_visited() -> None:
        manager.reset_all_hero_visited()
        logger.info("wyczyszczono listę odwiedzonych hero")
        visited_count.configure(text="0")

    el.cycle_reset_button(visited_row, command=on_clear_visited, text="Wyczyść")

    def on_bot_btn() -> None:
        if is_stopped():
            if on_start is not None:
                on_start()
        else:
            if on_stop is not None:
                on_stop()
        _sync_bot_btn()

    bot_btn = el.bot_button(btn_bar, command=on_bot_btn)

    def _sync_countdown() -> None:
        countdown.configure(text=el.format_countdown(remaining_sec(BOT)))
        raw_status = get_data(INFO_PATH, ALLIANCE_PIT_STATUS)
        status = raw_status if isinstance(raw_status, str) else None
        pit_status.configure(text=el.format_pit_status(status))
        # not_built — brak timera w grze; inaczej odliczanie z harmonogramu.
        if status == "not_built":
            pit_time.configure(text="—")
        else:
            pit_time.configure(
                text=el.format_countdown(remaining_sec(TASK_ALLIANCE_PIT))
            )
        visited_count.configure(text=str(len(manager.visited_ids)))
        root.after(250, _sync_countdown)

    def _sync_bot_btn() -> None:
        bot_btn.configure(text="Start" if is_stopped() else "Stop (F9)")
        root.after(200, _sync_bot_btn)

    mount_terminal(root)

    if on_ready is not None:
        root.after(0, on_ready)
    _sync_bot_btn()
    _sync_countdown()
    root.mainloop()


if __name__ == "__main__":
    run_ui()

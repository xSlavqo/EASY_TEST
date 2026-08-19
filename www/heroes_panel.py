"""Karta herosów — whitelist: dodaj, wyłącz, usuń, taski per postać."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from game.hero_manager import manager
from game.hero_manager.whitelist import (
    GATHER_RSS_LEVEL_MAX,
    GATHER_RSS_LEVEL_MIN,
    add_hero,
    load_whitelist,
    remove_hero,
    set_hero_enabled,
    set_hero_gather_rss_level,
    set_hero_task,
)
from log import logger
from state.settings import settings
from state.task_defs import TASK_DEFS


def _hero_has_custom_tasks(entry: dict) -> bool:
    """True gdy hero ma jawnie wyłączony choć jeden task."""
    tasks = entry.get("tasks") or {}
    return any(tasks.get(task.task_id) is False for task in TASK_DEFS)


def build_heroes_panel() -> Callable[[], None]:
    """Środkowa karta: lista postaci z heroes.json. Zwraca funkcję odświeżenia listy."""

    def _render_hero_list() -> None:
        list_box.clear()
        with list_box:
            items = load_whitelist()
            if not items:
                ui.label("brak").classes("text-grey")
                return
            for entry in items:
                enabled = bool(entry.get("enabled", True))
                nick = entry["nick"]
                uid = entry["uid"]
                hero_tasks = dict(entry.get("tasks") or {})
                nick_cls = "flex-grow min-w-0 truncate"
                if not enabled:
                    nick_cls += " text-grey"
                with ui.column().classes("w-full gap-0"):
                    with ui.row().classes("items-center gap-2 w-full flex-nowrap"):
                        ui.switch(
                            value=enabled,
                            on_change=lambda e, n=nick, u=uid: _on_toggle_hero(
                                n, u, bool(e.value)
                            ),
                        ).props("dense")
                        ui.label(nick).classes(nick_cls)
                        if _hero_has_custom_tasks(entry):
                            ui.label("*").classes("text-grey shrink-0").tooltip(
                                "własne ustawienia tasków"
                            )
                        ui.label(uid).classes("text-grey shrink-0")
                        ui.button(
                            "-",
                            on_click=lambda n=nick, u=uid: _on_remove_hero(n, u),
                        ).props("flat dense")

                    with ui.expansion("taski", icon="task_alt").classes(
                        "w-full ml-1"
                    ).props("dense header-class=py-1"):
                        if not enabled:
                            ui.label("postać wyłączona").classes(
                                "text-grey text-caption"
                            )
                        for task_def in TASK_DEFS:
                            global_on = bool(getattr(settings, task_def.settings_key))
                            hero_on = hero_tasks.get(task_def.task_id, True)
                            can_edit = enabled and global_on

                            def _on_task_toggle(
                                e,
                                n=nick,
                                u=uid,
                                tid=task_def.task_id,
                            ) -> None:
                                set_hero_task(n, u, tid, bool(e.value))
                                manager.reload_from_whitelist()
                                logger.info(
                                    "whitelist: %s task %s %s (%s)",
                                    "włączono" if e.value else "wyłączono",
                                    tid,
                                    n,
                                    u,
                                )
                                _render_hero_list()

                            row_cls = "items-center gap-1"
                            if not can_edit:
                                row_cls += " opacity-50"
                            with ui.row().classes(row_cls):
                                cb = ui.checkbox(
                                    task_def.label,
                                    value=hero_on,
                                    on_change=_on_task_toggle,
                                ).props("dense")
                                if not can_edit:
                                    cb.disable()
                                if not global_on:
                                    ui.icon("info").classes(
                                        "text-grey text-xs"
                                    ).tooltip("wyłączone globalnie")

                        with ui.row().classes("items-center gap-2 ml-1 mt-1"):
                            ui.label("RSS: poziom nodów").classes("text-caption")

                            def _on_rss_level(
                                e,
                                n=nick,
                                u=uid,
                            ) -> None:
                                try:
                                    level = int(e.value)
                                except (TypeError, ValueError):
                                    return
                                set_hero_gather_rss_level(n, u, level)
                                manager.reload_from_whitelist()
                                logger.info(
                                    "whitelist: %s RSS poziom %s (%s)",
                                    n,
                                    level,
                                    u,
                                )

                            rss_num = ui.number(
                                value=int(entry.get("gather_rss_level", 8)),
                                min=GATHER_RSS_LEVEL_MIN,
                                max=GATHER_RSS_LEVEL_MAX,
                                step=1,
                                on_change=_on_rss_level,
                            ).props("dense outlined").classes("w-20")
                            if not enabled:
                                rss_num.disable()

    def _on_add_hero() -> None:
        nick = str(nick_in.value or "").strip()
        uid = str(uid_in.value or "").strip()
        if not nick or not uid:
            ui.notify("wypełnij nick i uid", type="warning")
            return
        if not uid.isdigit():
            ui.notify("uid tylko cyfry", type="warning")
            return
        if not add_hero(nick, uid):
            ui.notify("taki hero już jest", type="warning")
            return
        logger.info("whitelist: dodano %s (%s)", nick, uid)
        nick_in.set_value("")
        uid_in.set_value("")
        manager.reload_from_whitelist()
        _render_hero_list()

    def _on_remove_hero(nick: str, uid: str) -> None:
        remove_hero(nick, uid)
        logger.info("whitelist: usunięto %s (%s)", nick, uid)
        manager.reload_from_whitelist()
        _render_hero_list()

    def _on_toggle_hero(nick: str, uid: str, enabled: bool) -> None:
        set_hero_enabled(nick, uid, enabled)
        manager.reload_from_whitelist()
        logger.info(
            "whitelist: %s %s (%s)",
            "włączono" if enabled else "wyłączono",
            nick,
            uid,
        )
        _render_hero_list()

    with ui.card().classes(
        "w-full md:w-96 shrink-0 md:h-full overflow-auto bg-[#383838]"
    ):
        ui.label("Herosi").classes("text-subtitle1")
        ui.label("przełącznik wyłącza postać · taski per postać").classes(
            "text-grey text-caption"
        )

        nick_in = ui.input("nick").props("dense outlined").classes("w-full")

        def _uid_digits_only(e) -> None:
            raw = str(e.value or "")
            digits = "".join(ch for ch in raw if ch.isdigit())
            if digits != raw:
                e.sender.set_value(digits)

        uid_in = (
            ui.input(
                "uid",
                on_change=_uid_digits_only,
            )
            .props("dense outlined inputmode=numeric")
            .classes("w-full")
        )

        ui.button("Dodaj herosa", on_click=_on_add_hero).props("flat dense").classes(
            "mt-1"
        )
        list_box = ui.column().classes("w-full gap-1 mt-2")
        _render_hero_list()

    return _render_hero_list

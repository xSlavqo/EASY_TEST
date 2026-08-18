"""Karta herosów — whitelist: dodaj, wyłącz, usuń."""

from __future__ import annotations

from nicegui import ui

from game.hero_manager import manager
from game.hero_manager.whitelist import (
    add_hero,
    load_whitelist,
    remove_hero,
    set_hero_enabled,
)
from log import logger


def build_heroes_panel() -> None:
    """Środkowa karta: lista postaci z heroes.json."""
    with ui.card().classes(
        "w-full md:w-96 shrink-0 md:h-full overflow-auto bg-[#383838]"
    ):
        ui.label("Herosi").classes("text-subtitle1")
        ui.label("przełącznik wyłącza (nie usuwa)").classes("text-grey text-caption")

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

        def _render_hero_list() -> None:
            list_box.clear()
            with list_box:
                items = load_whitelist()
                if not items:
                    ui.label("brak").classes("text-grey")
                    return
                for entry in items:
                    enabled = bool(entry.get("enabled", True))
                    nick_cls = "flex-grow min-w-0 truncate"
                    if not enabled:
                        nick_cls += " text-grey"
                    with ui.row().classes("items-center gap-2 w-full flex-nowrap"):
                        ui.switch(
                            value=enabled,
                            on_change=lambda e, n=entry["nick"], u=entry["uid"]: _on_toggle_hero(
                                n, u, bool(e.value)
                            ),
                        ).props("dense")
                        ui.label(entry["nick"]).classes(nick_cls)
                        ui.label(entry["uid"]).classes("text-grey shrink-0")
                        ui.button(
                            "-",
                            on_click=lambda n=entry["nick"], u=entry["uid"]: _on_remove_hero(
                                n, u
                            ),
                        ).props("flat dense")

        ui.button("Dodaj herosa", on_click=_on_add_hero).props("flat dense").classes(
            "mt-1"
        )
        list_box = ui.column().classes("w-full gap-1 mt-2")
        _render_hero_list()

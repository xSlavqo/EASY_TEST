"""Siatka kart herosów — podgląd + edycja whitelist."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from game.hero_manager import manager
from game.hero_manager.hero import Hero
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
from state.keys import alliance_rss_schedule_id, scount_sentry_post_schedule_id
from state.schedule import remaining_sec
from state.settings import settings
from state.task_defs import TASK_DEFS
from tasks.alliance_pit import pit_heroes_in_pit_for_ui
from www.formatters import format_countdown_short

# Skróty na chipach kart.
_TASK_SHORT: dict[str, str] = {
    "alliance_rss": "RSS",
    "alliance_pit": "Pit",
    "gather_buff": "Buff",
    "gather_rss": "Gather",
    "scount_sentry_post": "SSP",
}

_CHIP_CLASSES = {
    "due": "bg-green-700 text-white",
    "cd": "bg-amber-800 text-amber-100",
    "on": "bg-blue-900 text-blue-100",
    "hero_off": "bg-neutral-600 text-neutral-300",
    "global_off": "bg-neutral-800 text-neutral-500 line-through",
}


def _hero_has_custom_tasks(entry: dict) -> bool:
    """True gdy hero ma jawnie wyłączony choć jeden task."""
    tasks = entry.get("tasks") or {}
    return any(tasks.get(task.task_id) is False for task in TASK_DEFS)


def _rss_remaining(uid: str, nick: str) -> float | None:
    return remaining_sec(alliance_rss_schedule_id(uid, nick))


def _ssp_remaining(uid: str, nick: str) -> float | None:
    return remaining_sec(scount_sentry_post_schedule_id(uid, nick))


def _task_state(entry: dict, task_id: str, settings_key: str) -> str:
    """
    Stan chipu:
    - global_off / hero_off / due / cd / on
    """
    if not bool(getattr(settings, settings_key)):
        return "global_off"
    if not bool(entry.get("enabled", True)):
        return "hero_off"
    hero_tasks = entry.get("tasks") or {}
    if hero_tasks.get(task_id, True) is False:
        return "hero_off"

    uid = entry["uid"]
    nick = entry["nick"]
    if task_id == "alliance_rss":
        rem = _rss_remaining(uid, nick)
        if rem is not None and rem <= 0:
            return "due"
        if rem is not None:
            return "cd"
    if task_id == "scount_sentry_post":
        rem = _ssp_remaining(uid, nick)
        if rem is not None and rem <= 0:
            return "due"
        if rem is not None:
            return "cd"
    return "on"


def _is_due_entry(entry: dict) -> bool:
    if not bool(entry.get("enabled", True)):
        return False
    for task_def in TASK_DEFS:
        if task_def.task_id not in ("alliance_rss", "scount_sentry_post"):
            continue
        if _task_state(entry, task_def.task_id, task_def.settings_key) == "due":
            return True
    return False


def _visited_keys() -> set[str]:
    return {hero.key for hero in manager.heroes if hero.visited}


def _in_pit_keys() -> set[str]:
    return set(pit_heroes_in_pit_for_ui())


def build_heroes_panel() -> Callable[[], None]:
    """Siatka kart z heroes.json. Zwraca funkcję odświeżenia."""
    filter_mode = {"value": "all"}  # all | enabled | due
    sort_mode = {"value": "due"}  # due | nick
    # key → (rss_lbl, ssp_lbl) do odświeżania timerów bez przebudowy siatki
    timer_labels: dict[str, tuple[object, object]] = {}

    with ui.column().classes("w-full gap-2 min-w-0 flex-grow"):
        ui.label("Herosi").classes("text-subtitle1")
        ui.label(
            "karty: podgląd stanu · rozwinięcie „taski” = edycja"
        ).classes("text-grey text-caption")

        with ui.row().classes("items-end gap-2 flex-wrap w-full"):
            nick_in = ui.input("nick").props("dense outlined").classes("w-40")

            def _uid_digits_only(e) -> None:
                raw = str(e.value or "")
                digits = "".join(ch for ch in raw if ch.isdigit())
                if digits != raw:
                    e.sender.set_value(digits)

            uid_in = (
                ui.input("uid", on_change=_uid_digits_only)
                .props("dense outlined inputmode=numeric")
                .classes("w-36")
            )
            ui.button("Dodaj", on_click=lambda: _on_add_hero()).props("flat dense")

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("Pokaż:").classes("text-grey")

            def _set_filter(mode: str) -> None:
                filter_mode["value"] = mode
                render_grid()

            ui.button("wszyscy", on_click=lambda: _set_filter("all")).props(
                "flat dense"
            )
            ui.button("włączeni", on_click=lambda: _set_filter("enabled")).props(
                "flat dense"
            )
            ui.button("due", on_click=lambda: _set_filter("due")).props("flat dense")

            ui.separator().props("vertical")
            ui.label("Sortuj:").classes("text-grey")

            def _set_sort(mode: str) -> None:
                sort_mode["value"] = mode
                render_grid()

            ui.button("due ↑", on_click=lambda: _set_sort("due")).props("flat dense")
            ui.button("A→Z", on_click=lambda: _set_sort("nick")).props("flat dense")

        grid_box = ui.element("div").classes(
            "w-full grid gap-3 items-start "
            "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        )

    def _filtered(items: list[dict]) -> list[dict]:
        mode = filter_mode["value"]
        if mode == "enabled":
            items = [e for e in items if bool(e.get("enabled", True))]
        elif mode == "due":
            items = [e for e in items if _is_due_entry(e)]
        if sort_mode["value"] == "nick":
            items.sort(key=lambda e: str(e["nick"]).lower())
        else:
            items.sort(
                key=lambda e: (
                    0 if _is_due_entry(e) else 1,
                    str(e["nick"]).lower(),
                )
            )
        return items

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
        render_grid()

    def _on_remove_hero(nick: str, uid: str) -> None:
        remove_hero(nick, uid)
        logger.info("whitelist: usunięto %s (%s)", nick, uid)
        manager.reload_from_whitelist()
        render_grid()

    def _on_toggle_hero(nick: str, uid: str, enabled: bool) -> None:
        set_hero_enabled(nick, uid, enabled)
        manager.reload_from_whitelist()
        logger.info(
            "whitelist: %s %s (%s)",
            "włączono" if enabled else "wyłączono",
            nick,
            uid,
        )
        render_grid()

    def _render_card(
        entry: dict,
        *,
        in_pit: set[str],
        visited: set[str],
        current: Hero | None,
    ) -> None:
        enabled = bool(entry.get("enabled", True))
        nick = entry["nick"]
        uid = entry["uid"]
        key = f"{uid}/{nick}"
        hero_tasks = dict(entry.get("tasks") or {})
        gather_level = int(entry.get("gather_rss_level", 8))
        due = _is_due_entry(entry)

        card_cls = "bg-[#383838] border border-neutral-600"
        if due:
            card_cls += " ring-1 ring-green-600"
        if not enabled:
            card_cls += " opacity-60"

        with ui.card().classes(card_cls):
            with ui.row().classes("items-center gap-2 w-full flex-nowrap"):
                ui.switch(
                    value=enabled,
                    on_change=lambda e, n=nick, u=uid: _on_toggle_hero(
                        n, u, bool(e.value)
                    ),
                ).props("dense")
                ui.label(nick).classes("font-bold flex-grow min-w-0 truncate")
                if _hero_has_custom_tasks(entry):
                    ui.label("*").classes("text-amber-400 shrink-0").tooltip(
                        "własne ustawienia tasków"
                    )
                if key in in_pit:
                    ui.badge("w picie", color="orange").props("dense")
                if key in visited:
                    ui.icon("check_circle").classes(
                        "text-green-500 text-sm"
                    ).tooltip("odwiedzony w cyklu")
                if current is not None and current.key == key:
                    ui.icon("person").classes("text-blue-400 text-sm").tooltip(
                        "zalogowany"
                    )
                ui.button(
                    "-",
                    on_click=lambda n=nick, u=uid: _on_remove_hero(n, u),
                ).props("flat dense")

            ui.label(uid).classes("text-caption text-grey -mt-1 mb-2")

            with ui.row().classes("gap-1 flex-wrap"):
                for task_def in TASK_DEFS:
                    state = _task_state(
                        entry, task_def.task_id, task_def.settings_key
                    )
                    short = _TASK_SHORT.get(task_def.task_id, task_def.task_id)
                    ui.label(short).classes(
                        f"text-xs px-1.5 py-0.5 rounded cursor-default "
                        f"{_CHIP_CLASSES[state]}"
                    ).tooltip(f"{task_def.label} — {state}")

            with ui.row().classes("gap-4 mt-2 text-sm"):
                rss_lbl = ui.label(
                    f"RSS: {format_countdown_short(_rss_remaining(uid, nick))}"
                )
                ssp_lbl = ui.label(
                    f"SSP: {format_countdown_short(_ssp_remaining(uid, nick))}"
                )
                if gather_level != 8:
                    ui.label(f"nod: {gather_level}").classes("text-grey")

            with ui.expansion("taski", icon="tune").classes("w-full mt-1").props(
                "dense"
            ):
                if not enabled:
                    ui.label("postać wyłączona").classes("text-grey text-caption")
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
                        render_grid()

                    row_cls = "items-center gap-1"
                    if not can_edit:
                        row_cls += " opacity-50"
                    with ui.row().classes(row_cls):
                        cb = ui.checkbox(
                            task_def.label,
                            value=bool(hero_on),
                            on_change=_on_task_toggle,
                        ).props("dense")
                        if not can_edit:
                            cb.disable()
                        if not global_on:
                            ui.icon("info").classes("text-grey text-xs").tooltip(
                                "wyłączone globalnie"
                            )

                with ui.row().classes("items-center gap-2 ml-1 mt-1"):
                    ui.label("RSS: poziom nodów").classes("text-caption")

                    def _on_rss_level(e, n=nick, u=uid) -> None:
                        try:
                            level = int(e.value)
                        except (TypeError, ValueError):
                            return
                        set_hero_gather_rss_level(n, u, level)
                        manager.reload_from_whitelist()
                        logger.info(
                            "whitelist: %s RSS poziom %s (%s)", n, level, u
                        )

                    rss_num = (
                        ui.number(
                            value=gather_level,
                            min=GATHER_RSS_LEVEL_MIN,
                            max=GATHER_RSS_LEVEL_MAX,
                            step=1,
                            on_change=_on_rss_level,
                        )
                        .props("dense outlined")
                        .classes("w-20")
                    )
                    if not enabled:
                        rss_num.disable()

            timer_labels[key] = (rss_lbl, ssp_lbl)

    def render_grid() -> None:
        timer_labels.clear()
        items = _filtered(list(load_whitelist()))
        in_pit = _in_pit_keys()
        visited = _visited_keys()
        current = Hero.current()
        grid_box.clear()
        with grid_box:
            if not items:
                ui.label("brak pasujących hero").classes("text-grey col-span-full")
                return
            for entry in items:
                _render_card(
                    entry, in_pit=in_pit, visited=visited, current=current
                )

    def _refresh_timers() -> None:
        for key, (rss_lbl, ssp_lbl) in list(timer_labels.items()):
            if "/" not in key:
                continue
            uid, nick = key.split("/", 1)
            try:
                rss_lbl.set_text(  # type: ignore[attr-defined]
                    f"RSS: {format_countdown_short(_rss_remaining(uid, nick))}"
                )
                ssp_lbl.set_text(  # type: ignore[attr-defined]
                    f"SSP: {format_countdown_short(_ssp_remaining(uid, nick))}"
                )
            except Exception:
                # Element mógł zostać usunięty przy przebudowie siatki.
                timer_labels.pop(key, None)

    render_grid()
    ui.timer(1.0, _refresh_timers)
    return render_grid

"""Whitelist postaci — nick + uid w data/heroes.json."""

from __future__ import annotations

from pathlib import Path

from state.task_defs import TASK_IDS
from state.store import get_data, save_data

_ROOT = Path(__file__).resolve().parent.parent.parent
HEROES_PATH = _ROOT / "data" / "heroes.json"


def add_hero(nick: str, uid: str) -> bool:
    """Dopisz parę nick+uid. False gdy puste pola, uid nie z cyfr albo duplikat."""
    nick = nick.strip()
    uid = uid.strip()
    if not nick or not uid.isdigit():
        return False
    items = load_whitelist()
    for entry in items:
        if entry["uid"] == uid and entry["nick"] == nick:
            return False
    items.append({"uid": uid, "nick": nick, "enabled": True})
    save_data(HEROES_PATH, "whitelist", items)
    return True


def remove_hero(nick: str, uid: str) -> None:
    """Usuń parę nick+uid z listy."""
    items = [
        entry
        for entry in load_whitelist()
        if not (entry["uid"] == uid and entry["nick"] == nick)
    ]
    save_data(HEROES_PATH, "whitelist", items)


def set_hero_enabled(nick: str, uid: str, enabled: bool) -> None:
    """Włącz / wyłącz postać. Zostaje na liście, bot ją pomija gdy False."""
    items = load_whitelist()
    for entry in items:
        if entry["uid"] == uid and entry["nick"] == nick:
            entry["enabled"] = bool(enabled)
            break
    save_data(HEROES_PATH, "whitelist", items)


def set_hero_task(nick: str, uid: str, task_id: str, enabled: bool) -> None:
    """Włącz / wyłącz pojedynczy task u postaci."""
    if task_id not in TASK_IDS:
        return
    items = load_whitelist()
    for entry in items:
        if entry["uid"] == uid and entry["nick"] == nick:
            tasks = dict(entry.get("tasks", {}))
            tasks[task_id] = bool(enabled)
            entry["tasks"] = tasks
            break
    save_data(HEROES_PATH, "whitelist", items)


def _parse_tasks(raw: object) -> dict[str, bool]:
    """tasks z JSON — tylko znane klucze i wartości bool."""
    if not isinstance(raw, dict):
        return {}
    tasks: dict[str, bool] = {}
    for key, value in raw.items():
        if key not in TASK_IDS:
            continue
        if value is True or value is False:
            tasks[key] = bool(value)
    return tasks


def load_whitelist() -> list[dict]:
    """Lista wpisów {"uid", "nick", "enabled", "tasks?"} z dysku."""
    raw = get_data(HEROES_PATH, "whitelist", default=[])
    if not isinstance(raw, list):
        return []
    items: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        uid = str(entry.get("uid", "")).strip()
        nick = str(entry.get("nick", "")).strip()
        if not uid.isdigit() or not nick:
            continue
        enabled = entry.get("enabled", True)
        if enabled is not True and enabled is not False:
            enabled = True
        tasks = _parse_tasks(entry.get("tasks"))
        item: dict = {"uid": uid, "nick": nick, "enabled": bool(enabled)}
        if tasks:
            item["tasks"] = tasks
        items.append(item)
    return items

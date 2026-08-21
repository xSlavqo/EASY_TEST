"""Uniwersalny zapis klucz → wartość w plikach JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_io import load_file, mutate_file

_ROOT = Path(__file__).resolve().parent.parent
INFO_PATH = _ROOT / "data" / "info.json"


def _get_nested(data: dict, key: str) -> Any:
    parts = key.split(".")
    node: Any = data
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set_nested(data: dict, key: str, value: Any) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _delete_nested(data: dict, key: str) -> bool:
    parts = key.split(".")
    node: Any = data
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    if not isinstance(node, dict) or parts[-1] not in node:
        return False
    del node[parts[-1]]
    return True


def get_data(path: Path, key: str, default: Any = None) -> Any:
    """Odczytaj wartość po kluczu z kropkami (np. schedule.next_run_at)."""
    value = _get_nested(load_file(path), key)
    return default if value is None else value


def save_data(path: Path, key: str, value: Any) -> None:
    """Zapisz wartość pod kluczem z kropkami (RMW pod jednym lockiem)."""

    def _apply(data: dict) -> bool:
        _set_nested(data, key, value)
        return True

    mutate_file(path, _apply)


def delete_data(path: Path, key: str) -> None:
    """Usuń klucz z pliku JSON."""
    mutate_file(path, lambda data: _delete_nested(data, key))

"""
Niski poziom: jak bezpiecznie czytać i pisać cały plik JSON.

Używane przez store.py. Sam bot zwykle woła store.get_data / save_data, nie to.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

# Jeden lock na ścieżkę — bot + WWW nie kolidują przy replace na Windows.
_locks_guard = threading.Lock()
_path_locks: dict[str, threading.Lock] = {}

_REPLACE_ATTEMPTS = 20
_REPLACE_DELAY_SEC = 0.05


def ensure_parent_dir(path: Path) -> None:
    """Utwórz katalog nadrzędny pliku, jeśli nie istnieje."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _lock_for(path: Path) -> threading.Lock:
    """Zwróć (lub stwórz) lock dla tej ścieżki — jeden na plik w całym procesie."""
    key = str(path.resolve())
    with _locks_guard:
        lock = _path_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _path_locks[key] = lock
        return lock


def _read_dict(path: Path) -> dict:
    """Wczytaj cały JSON do słownika. Bez locka — wołaj tylko z _lock_for."""
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_dict(path: Path, data: dict) -> None:
    """Zapisz słownik do JSON przez plik .tmp. Bez locka — wołaj tylko z _lock_for."""
    ensure_parent_dir(path)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        _replace_with_retry(tmp, path)
    finally:
        if tmp.is_file():
            try:
                tmp.unlink()
            except OSError:
                pass


def _replace_with_retry(tmp: Path, path: Path) -> None:
    """Podmień tmp na docelowy plik; na Windowsie powtórz przy zajętym pliku."""
    last_error: BaseException | None = None
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            tmp.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
        except OSError as exc:
            # WinError 5 = odmowa, 32 = plik zajęty.
            winerror = getattr(exc, "winerror", None)
            if winerror not in (5, 32):
                raise
            last_error = exc
        time.sleep(_REPLACE_DELAY_SEC * (1 + attempt * 0.25))

    assert last_error is not None
    raise last_error


def load_file(path: Path) -> dict:
    """Wczytaj cały plik JSON pod lockiem. Brak pliku / błąd → pusty słownik."""
    with _lock_for(path):
        return _read_dict(path)


def save_file_atomic(path: Path, data: dict) -> None:
    """Zapisz cały słownik do JSON pod lockiem (przez plik tymczasowy)."""
    with _lock_for(path):
        _write_dict(path, data)


def mutate_file(path: Path, mutator: Callable[[dict], bool]) -> None:
    """
    Odczyt → zmiana w pamięci → zapis, wszystko pod jednym lockiem.

    mutator(data) zwraca True = zapisz; False = nic nie zapisuj.
    """
    with _lock_for(path):
        data = _read_dict(path)
        if mutator(data):
            _write_dict(path, data)

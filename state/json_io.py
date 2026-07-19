"""Niskopoziomowy odczyt i zapis plików JSON."""

from __future__ import annotations

import json
from pathlib import Path


def ensure_parent_dir(path: Path) -> None:
    """Utwórz katalog nadrzędny pliku, jeśli nie istnieje."""
    path.parent.mkdir(parents=True, exist_ok=True)


def load_file(path: Path) -> dict:
    """Wczytaj JSON; brak pliku lub błąd parsowania → pusty słownik."""
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_file_atomic(path: Path, data: dict) -> None:
    """Zapisz JSON atomowo przez plik tymczasowy."""
    ensure_parent_dir(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)

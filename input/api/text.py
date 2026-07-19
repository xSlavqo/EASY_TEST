"""Odczyt tekstu z regionu ekranu."""

from __future__ import annotations

from ..engine.ocr import read_text_from_image
from ..engine.vision import screenshot

Region = tuple[int, int, int, int]


def get_text(region: Region, allowlist: str) -> str | None:
    """Zrzut regionu i OCR. Zwraca pełny odczytany tekst lub None."""
    roi = screenshot(region)
    return read_text_from_image(roi, allowlist)

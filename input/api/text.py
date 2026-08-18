"""Odczyt tekstu z regionu ekranu."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input.engine.ocr import read_text_from_image
from input.engine.vision import screenshot

Region = tuple[int, int, int, int]


def get_text(region: Region, allowlist: str, *, contrast: bool = False) -> str | None:
    """Zrzut regionu i OCR. Zwraca pełny odczytany tekst lub None.

    contrast=True — szary tekst na białym (np. linia uid konta) robi się ciemniejszy.
    """
    roi = screenshot(region)
    return read_text_from_image(roi, allowlist, contrast=contrast)

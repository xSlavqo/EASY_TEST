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


def get_text(region: Region, allowlist: str) -> str | None:
    """Zrzut regionu i OCR. Zwraca pełny odczytany tekst lub None."""
    roi = screenshot(region)
    return read_text_from_image(roi, allowlist)


# --- test ręczny (Code Runner / python input/api/text.py) ---
# coord_picker - 1920x1080 — ZA DUŻY na OCR (cała karta); zostawiony jako referencja.
# _TEST_REGION: Region = (364, 387, 1205, 585)
# Wąski ROI na status/timer — podmień na dokładny wycinek z coord_picker.
_TEST_REGION: Region = (364, 387, 1205, 585)
_TEST_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:/"


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(f"region={_TEST_REGION} allowlist={_TEST_ALLOWLIST!r}", flush=True)
    w, h = _TEST_REGION[2], _TEST_REGION[3]
    if w * h > 80_000:
        print(
            f"UWAGA: region {w}x{h} jest duży — OCR (upscale x6) może trwać długo lub wyglądać jak hang",
            flush=True,
        )
    print("zrzut + EasyOCR (pierwsze odpalenie ładuje modele — cierpliwie)...", flush=True)
    print(f"OCR → {get_text(_TEST_REGION, _TEST_ALLOWLIST)!r}", flush=True)

"""
OCR — EasyOCR na wycinku ekranu (preprocessing + singleton reader).
"""

from __future__ import annotations

import warnings

import cv2
import numpy as np

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module=r"torch\.utils\.data\.dataloader",
)

_DEFAULT_UPSCALE = 6.0
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr

        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


def _stretch_contrast(gray: np.ndarray) -> np.ndarray:
    """Szary napis na białym → ciemniejszy. Najciemniejsze piksele ≈ czarne, tło ≈ białe."""
    lo, hi = np.percentile(gray, (2, 98))
    if hi <= lo + 1:
        return gray
    scale = 255.0 / (hi - lo)
    out = (gray.astype(np.float32) - lo) * scale
    return np.clip(out, 0, 255).astype(np.uint8)


def _preprocess_roi(
    roi_bgr: np.ndarray,
    *,
    upscale: float = _DEFAULT_UPSCALE,
    contrast: bool = False,
) -> np.ndarray:
    """Przygotuj mały ROI pod OCR — upscale + grayscale (bez binaryzacji Otsu)."""
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    if upscale != 1.0:
        gray = cv2.resize(gray, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    if contrast:
        gray = _stretch_contrast(gray)
    return gray


def read_text_from_image(
    roi_bgr: np.ndarray,
    allowlist: str,
    *,
    contrast: bool = False,
) -> str | None:
    """Odczytaj tekst z obrazu BGR. Zwraca pełny tekst lub None gdy brak wykrycia."""
    processed = _preprocess_roi(roi_bgr, contrast=contrast)
    reader = _get_reader()
    results = reader.readtext(processed, allowlist=allowlist, detail=0)
    text = "".join(results).strip() if results else ""
    return text or None


# Przy imporcie — błąd torch/DLL wychodzi na starcie, nie w środku cyklu.
_get_reader()

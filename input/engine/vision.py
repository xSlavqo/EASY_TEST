"""
Rozpoznawanie obrazu — dopasowanie szablonów i zrzuty ekranu.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import cv2
import mss
import numpy as np

_user32 = ctypes.windll.user32

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"

TemplateSource = str | Path | np.ndarray

_DEFAULT_THRESHOLD = 0.88
_ALPHA_THRESHOLD = 128
_MIN_MASK_PIXELS = 16

DEFAULT_THRESHOLD = _DEFAULT_THRESHOLD


@dataclass(frozen=True)
class _TemplateForMatch:
    bgr: np.ndarray
    mask: np.ndarray | None


@dataclass(frozen=True)
class Match:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class _MatchCandidate:
    match: Match
    score: float


@dataclass(frozen=True)
class SearchResult:
    match: Match
    score: float
    origin_x: int
    origin_y: int
    monitor: dict


def resolve_template(template: TemplateSource) -> Path | np.ndarray:
    """Rozwiąż szablon: ndarray bez zmian albo ścieżka do PNG w templates/."""
    if isinstance(template, np.ndarray):
        return template
    return resolve_template_path(template)


def resolve_template_path(template: str | Path) -> Path:
    """Rozwiąż ścieżkę do pliku PNG w folderze templates/."""
    path = Path(template)
    if path.is_file():
        return path.resolve()
    candidate = _TEMPLATES_DIR / path.name
    if candidate.is_file():
        return candidate.resolve()
    raise FileNotFoundError(f"Nie znaleziono szablonu: {template}")


def search_template(
    template: TemplateSource,
    threshold: float,
    *,
    region: tuple[int, int, int, int] | None = None,
) -> SearchResult | None:
    """Szukaj najlepszego dopasowania w regionie lub na całym ekranie."""
    monitor = primary_monitor()
    screen, origin_x, origin_y = capture_screen(region)
    best = _scan_best_match(screen, template)
    if best is None or best.score < threshold:
        return None

    return SearchResult(
        match=best.match,
        score=best.score,
        origin_x=origin_x,
        origin_y=origin_y,
        monitor=monitor,
    )


def capture_screen(region: tuple[int, int, int, int] | None) -> tuple[np.ndarray, int, int]:
    """Zrzut ekranu (BGR) i offset lewego górnego rogu."""
    with mss.MSS() as sct:
        if region is None:
            monitor = sct.monitors[1]
        else:
            left, top, width, height = region
            monitor = {"left": left, "top": top, "width": width, "height": height}
        raw = np.array(sct.grab(monitor))
        return raw[:, :, :3].copy(), monitor["left"], monitor["top"]


def screenshot(region: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """Zrzut ekranu (BGR) — cały ekran lub wskazany region."""
    screen, _, _ = capture_screen(region)
    return screen


def match_score(screen: np.ndarray, template: TemplateSource) -> float:
    """Najlepszy wynik dopasowania szablonu (0–1) bez progu; -1.0 gdy brak."""
    resolved = resolve_template(template)
    best = _scan_best_match(screen, resolved)
    return best.score if best is not None else -1.0


def primary_monitor() -> dict:
    """Metadane głównego monitora (współrzędne mss)."""
    with mss.MSS() as sct:
        return dict(sct.monitors[1])


def screen_scale() -> tuple[float, float]:
    """Przelicz piksele zrzutu na współrzędne kursora (DPI). Zwykle (1.0, 1.0)."""
    with mss.MSS() as sct:
        mon = sct.monitors[1]
        physical_w, physical_h = mon["width"], mon["height"]

    logical_w = _user32.GetSystemMetrics(0)
    logical_h = _user32.GetSystemMetrics(1)

    if physical_w <= 0 or physical_h <= 0:
        return 1.0, 1.0

    return logical_w / physical_w, logical_h / physical_h


def locate_template(
    template: TemplateSource,
    threshold: float,
    *,
    region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int] | None:
    """
    Znajdź szablon i zwróć absolutny region do kliknięcia (x, y, w, h) lub None.

    Współrzędne są już przeskalowane pod DPI (gotowe dla myszy).
    """
    resolved = resolve_template(template)
    result = search_template(resolved, threshold, region=region)
    if result is None:
        return None

    sx, sy = screen_scale()
    left = int((result.match.x + result.origin_x) * sx)
    top = int((result.match.y + result.origin_y) * sy)
    width = max(1, int(result.match.width * sx))
    height = max(1, int(result.match.height * sy))

    return left, top, width, height


def _scan_best_match(
    screen: np.ndarray,
    template: TemplateSource,
) -> _MatchCandidate | None:
    """Przeskanuj caly obszar w oryginalnej skali szablonu."""
    needle = _load_template_for_match(template)
    haystack = _as_bgr(screen)
    use_mask = needle.mask is not None
    method = cv2.TM_CCORR_NORMED if use_mask else cv2.TM_CCOEFF_NORMED

    tpl_h, tpl_w = needle.bgr.shape[:2]
    if tpl_h > haystack.shape[0] or tpl_w > haystack.shape[1]:
        return None

    if use_mask:
        result = cv2.matchTemplate(haystack, needle.bgr, method, mask=needle.mask)
    else:
        result = cv2.matchTemplate(haystack, needle.bgr, method)

    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    return _MatchCandidate(
        match=Match(x=max_loc[0], y=max_loc[1], width=tpl_w, height=tpl_h),
        score=float(max_val),
    )


def _load_template_for_match(template: TemplateSource) -> _TemplateForMatch:
    """Wczytaj szablon BGR; kanał alfy → maska (przezroczyste piksele ignorowane)."""
    img = _read_template_image(template)
    mask: np.ndarray | None = None

    if img.ndim == 3 and img.shape[2] == 4:
        bgr = _as_bgr(img[:, :, :3])
        alpha = img[:, :, 3]
        mask = np.where(alpha > _ALPHA_THRESHOLD, 255, 0).astype(np.uint8)
        if not mask.any() or int((mask > 0).sum()) < _MIN_MASK_PIXELS:
            mask = None
    else:
        bgr = _as_bgr(img)

    return _TemplateForMatch(bgr=bgr, mask=mask)


def _read_template_image(template: TemplateSource) -> np.ndarray:
    """Wczytaj surowy obraz szablonu (BGR lub BGRA)."""
    if isinstance(template, (str, Path)):
        img = cv2.imread(str(template), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Nie można wczytać szablonu: {template}")
        return img
    return template


def _as_bgr(img: np.ndarray) -> np.ndarray:
    """Upewnij sie, ze obraz jest BGR (bez edycji pikseli)."""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        return img[:, :, :3].copy()
    return img

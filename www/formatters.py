"""Teksty statusów panelu WWW."""

from __future__ import annotations

# PitPhase z tasks/alliance_pit.py (+ legacy building/gather).
_PIT_PHASE_LABELS = {
    "not_built": "nie wybudowane",
    "constructing": "budowanie",
    "built": "wybudowany",
    # legacy z JSON sprzed refaktoru
    "building": "budowanie",
    "gather": "wybudowany",
}


def format_countdown(remaining: float | None) -> str:
    """>=1h → h+min; <1h → min; <10min → min+s; <1min → s."""
    if remaining is None:
        return "—"
    if remaining <= 0:
        return "w trakcie"
    total = int(remaining)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours >= 1:
        return f"{hours} h {minutes} min"
    if minutes >= 10:
        return f"{minutes} min"
    if minutes >= 1:
        return f"{minutes} min {seconds} s"
    return f"{seconds} s"


def format_pit_time(phase: str | None, remaining: float | None) -> str:
    """constructing bez timera / brak → —; inaczej format_countdown z expires_at."""
    if phase in ("not_built", "constructing", "building"):
        if remaining is None:
            return "—"
    return format_countdown(remaining)


def format_pit_status(phase: str | None, remaining: float | None = None) -> str:
    """Etykieta fazy pitu (PitPhase)."""
    if not phase:
        return "—"
    label = _PIT_PHASE_LABELS.get(phase)
    if label:
        if phase in ("built", "gather") and (remaining is None or remaining <= 0):
            return "do sprawdzenia"
        return label
    return phase

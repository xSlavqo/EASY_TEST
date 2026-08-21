"""Teksty statusów panelu WWW."""

from __future__ import annotations

_PIT_STATUS_LABELS = {
    "not_built": "nie wybudowane",
    "building": "budowanie",
    "gather": "zbieranie",
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


def format_pit_time(status: str | None, remaining: float | None) -> str:
    """building bez timera / brak → —; inaczej format_countdown z expires_at."""
    if status == "not_built" or status == "building":
        if remaining is None:
            return "—"
    return format_countdown(remaining)


def format_pit_status(status: str | None, remaining: float | None = None) -> str:
    """Etykieta stanu pitu."""
    if not status:
        return "—"
    if status == "building":
        return _PIT_STATUS_LABELS["building"]
    if status == "not_built":
        return _PIT_STATUS_LABELS["not_built"]
    if remaining is None or remaining <= 0:
        return "do sprawdzenia"
    return _PIT_STATUS_LABELS.get(status, status)

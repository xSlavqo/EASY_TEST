"""Jedna postać — nick, uid konta, stan."""

from __future__ import annotations


class Hero:
    """Jedna postać z whitelist: nick (unikalny) + uid (konto, może mieć wiele nicków)."""

    def __init__(self, nick: str, uid: str, *, enabled: bool = True) -> None:
        self.nick = nick
        self.uid = uid
        self.enabled = enabled
        self.logged_in = False
        self.visited = False
        # None = jeszcze nie odczytane; "brak" = OCR "-" (bez sojuszu).
        self.alliance: str | None = None
        # Id tej postaci z przeglądu (to NIE uid konta).
        self.hero_id: str | None = None
        # PDW z przeglądu: aktualne / max (np. 1480/1480).
        self.pdw: int | None = None
        self.pdw_max: int | None = None

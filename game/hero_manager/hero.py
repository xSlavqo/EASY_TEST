"""Jedna postać — nick, uid konta, stan."""

from __future__ import annotations

import re


def fold_nick(nick: str) -> str:
    """OCR: 1/l/I oraz o/0 przy cyfrach traktujemy jak ten sam znak."""
    s = nick.casefold().replace("l", "1").replace("i", "1")
    s = re.sub(r"(?<=\d)o", "0", s)
    s = re.sub(r"o(?=\d)", "0", s)
    return s


class Hero:
    """Jedna postać z whitelist: nick (unikalny) + uid (konto, może mieć wiele nicków)."""

    def __init__(
        self,
        nick: str,
        uid: str,
        *,
        enabled: bool = True,
        tasks: dict[str, bool] | None = None,
    ) -> None:
        self.nick = nick
        self.uid = uid
        self.enabled = enabled
        # Brak klucza = domyślnie włączone (gdy global też wł.).
        self.tasks: dict[str, bool] = dict(tasks or {})
        self.logged_in = False
        self.visited = False
        # None = jeszcze nie odczytane; "brak" = OCR "-" (bez sojuszu).
        self.alliance: str | None = None
        # Id tej postaci z przeglądu (to NIE uid konta).
        self.hero_id: str | None = None
        # PDW z przeglądu: aktualne / max (np. 1480/1480).
        self.pdw: int | None = None
        self.pdw_max: int | None = None

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

    _current: Hero | None = None

    @classmethod
    def current(cls) -> Hero | None:
        """Zalogowany bohater (max jeden na całą aplikację), albo None."""
        return cls._current

    @classmethod
    def clear_logged_in(cls) -> None:
        """Zdejmij zalogowanego — np. nieznany nick albo brak OCR."""
        cls._current = None

    def __init__(
        self,
        nick: str,
        uid: str,
        *,
        enabled: bool = True,
        tasks: dict[str, bool] | None = None,
        gather_rss_level: int = 8,
    ) -> None:
        self.nick = nick
        self.uid = uid
        self.enabled = enabled  # włącznik w panelu WWW

        # Taski tej postaci: brak klucza = włączone (o ile global też wł.).
        self.tasks: dict[str, bool] = dict(tasks or {})
        self.gather_rss_level = gather_rss_level  # poziom nodów RSS (1–10)

        self.visited = False  # już obsłużony w bieżącym cyklu bota

        # Poniżej: odczyt z ekranu przeglądu postaci (current_hero).
        self.alliance: str | None = None  # None = nie wiemy; "brak" = bez sojuszu
        self.hero_id: str | None = None  # id postaci w grze — to nie uid konta
        self.pdw: int | None = None  # aktualne PDW, np. 1480 z "1480/1480"
        self.pdw_max: int | None = None  # max PDW z tego samego OCR

    @property
    def key(self) -> str:
        """Identyfikator postaci w JSON / pit / visited: uid/nick."""
        return f"{self.uid}/{self.nick}"

    @property
    def logged_in(self) -> bool:
        return Hero._current is self

    @logged_in.setter
    def logged_in(self, value: bool) -> None:
        if value:
            Hero._current = self
        elif Hero._current is self:
            Hero._current = None

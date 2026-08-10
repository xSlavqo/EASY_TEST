"""Jedna postać — dane i stan bohatera."""

from __future__ import annotations

from pathlib import Path


class Hero:
    """Jedna postać — email konta (z folderu = przypisany do main.png), awatary, stan."""

    def __init__(
        self,
        email: str,
        hero_id: str,
        main: Path,
        swap: Path | None,
    ) -> None:
        # Adres konta z templates/heroes/<email>/... — ten sam email idzie do account_swap (OCR).
        self.email = email
        self.id = hero_id
        self.main = main
        self.swap = swap
        self.logged_in = False
        self.visited = False
        # None = brak sojuszu; str = ID sojuszu (na razie stałe MZ2).
        self.alliance: str | None = "MZ2"

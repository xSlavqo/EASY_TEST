"""
Akcje na szablonach ekranu — znajdź, czekaj, kliknij.
"""

from __future__ import annotations

import random
import time

from .click import click_region
from ..engine.vision import TemplateSource, locate_template, resolve_template, search_template
from state.stop import check_stop, sleep as stop_sleep

DEFAULT_THRESHOLD = 0.99

DEFAULT_FIND_CLICK_TIMEOUT = 30.0
DEFAULT_FIND_ON_SCREEN_TIMEOUT = 0.0
DEFAULT_WAIT_ANY_TIMEOUT = 120.0

# Szukanie szablonu co 0.5 s (gdy nie ma popupu do zamknięcia).
DEFAULT_POLL_INTERVAL = (0.5, 0.5)
DEFAULT_WAIT_INITIAL_DELAY = 0.0

DEFAULT_CLICK_MARGIN = 0.15


def _on_no_match(poll_interval: tuple[float, float] = DEFAULT_POLL_INTERVAL) -> None:
    """
    Brak szablonu: zamknij znany popup i szukaj od razu;
    gdy popupów nie ma — poczekaj i szukaj dalej.
    """
    # Import tu, nie na górze pliku: input nie może ładować game przy starcie
    # (game i tak importuje input — byłby import w kółko).
    from game.popups import dismiss_popups

    if dismiss_popups():
        return
    stop_sleep(random.uniform(*poll_interval))


def find_and_click(
    template: TemplateSource,
    *,
    region: tuple[int, int, int, int] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_FIND_CLICK_TIMEOUT,
    poll_interval: tuple[float, float] = DEFAULT_POLL_INTERVAL,
    margin: float = DEFAULT_CLICK_MARGIN,
    offset_x: int = 0,
    offset_y: int = 0,
) -> bool:
    """
    Znajdź szablon na ekranie i kliknij. Zwraca True przy sukcesie.

    offset_x/offset_y przesuwają punkt kliknięcia względem znalezionego obrazu
    (np. klik obok landmarku).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_stop()
        rect = locate_template(template, threshold, region=region)
        if rect is not None:
            click_region(*rect, margin=margin, offset_x=offset_x, offset_y=offset_y)
            return True
        _on_no_match(poll_interval)

    return False


def find_on_screen(
    template: TemplateSource,
    *,
    region: tuple[int, int, int, int] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_FIND_ON_SCREEN_TIMEOUT,
    poll_interval: tuple[float, float] = DEFAULT_POLL_INTERVAL,
) -> bool:
    """Sprawdź czy szablon jest widoczny na ekranie (bez klikania)."""
    deadline = time.monotonic() + timeout if timeout > 0 else time.monotonic()

    resolved = resolve_template(template)

    while True:
        check_stop()
        result = search_template(resolved, threshold, region=region)
        if result is not None:
            return True

        if time.monotonic() >= deadline:
            return False

        _on_no_match(poll_interval)


def wait_for_any_on_screen(
    templates: list[TemplateSource],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_WAIT_ANY_TIMEOUT,
    initial_delay: float = DEFAULT_WAIT_INITIAL_DELAY,
    poll_interval: tuple[float, float] = DEFAULT_POLL_INTERVAL,
    region: tuple[int, int, int, int] | None = None,
) -> tuple[int, tuple[int, int, int, int]] | None:
    """
    Czekaj aż którykolwiek szablon pojawi się na ekranie.

    Zwraca (indeks w liście, rect x/y/w/h) albo None po timeout.
    """
    if initial_delay > 0:
        stop_sleep(initial_delay)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_stop()
        for index, template in enumerate(templates):
            rect = locate_template(template, threshold, region=region)
            if rect is not None:
                return index, rect
        _on_no_match(poll_interval)
    return None

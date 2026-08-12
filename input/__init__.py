"""Publiczne API wejścia bota."""

from .api.click import click_point, click_region, right_click_point
from .api.image import (
    DEFAULT_THRESHOLD,
    find_and_click,
    find_on_screen,
    wait_for_any_on_screen,
)
from .api.keyboard import press_key, type_text
from .api.text import get_text
from .engine.vision import (
    Match,
    SearchResult,
    TemplateSource,
    locate_template,
    match_score,
    screenshot,
    search_template,
)

__all__ = [
    "DEFAULT_THRESHOLD",
    "Match",
    "SearchResult",
    "TemplateSource",
    "click_point",
    "click_region",
    "find_and_click",
    "find_on_screen",
    "get_text",
    "locate_template",
    "match_score",
    "press_key",
    "right_click_point",
    "screenshot",
    "search_template",
    "type_text",
    "wait_for_any_on_screen",
]

"""
Wykrywanie zalogowanego bohatera — OCR nick / hero_id / sojusz / pdw.

To kawałek HeroManager — osobny plik, bo current_hero będzie się rozrastać.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import activate_window
from input import find_on_screen, get_text, locate_template, press_key
from log import logger
from state.stop import check_stop, request_stop, sleep as stop_sleep

from ..view_detector import in_game
from .hero import Hero, fold_nick

_CURRENT_HERO_ROUNDS = 5
_CURRENT_HERO_RETRY_DELAY_SEC = 10.0
_SETTING_BUTTON = _ROOT / "templates" / "navigation" / "setting_button.png"
_NICK_COPY = _ROOT / "templates" / "navigation" / "nick_copy.png"
_HERO_REVIEW_SEARCH_TIMEOUT = 3.0
_HERO_REVIEW_MAX_ESC = 8
_HERO_REVIEW_ESC_DELAY = (0.3, 0.6)
_DETECT_THRESHOLD = 0.99

# coord_picker 1920×1080 — lewy górny stały; szerokość nicku tnie przycisk kopiuj.
_NICK_MAX = (20, 269, 310, 36)
_HERO_ID_REGION = (326, 243, 90, 23)
_ALLIANCE_REGION = (16, 569, 124, 39)
_PDW_REGION = (191, 356, 96, 24)

_NICK_ALLOW = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-[]"
_HERO_ID_ALLOW = "0123456789"
_ALLIANCE_ALLOW = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=[]"
_PDW_ALLOW = "0123456789 /"

NO_ALLIANCE = "brak"


class CurrentHero:
    """Metody HeroManager: przegląd + OCR przeglądu postaci."""

    def current_hero(
        self,
        *,
        timeout: float = 60.0,
        poll: float = 5.0,
    ) -> bool | None:
        """
        OCR nick → ustaw logged_in, hero_id, alliance i pdw.

        True — nick na liście.
        None — nick odczytany, nie ma na whitelist (caller: swap).
        False — brak przeglądu / pusty OCR po rundach.
        """
        _ = timeout, poll

        for round_n in range(1, _CURRENT_HERO_ROUNDS + 1):
            check_stop()

            if round_n > 1:
                logger.warning(
                    "current_hero — brak odczytu, czekam %.0f s (runda %s/%s)",
                    _CURRENT_HERO_RETRY_DELAY_SEC,
                    round_n,
                    _CURRENT_HERO_ROUNDS,
                )
                stop_sleep(_CURRENT_HERO_RETRY_DELAY_SEC)

            if not self._go_to_hero_review():
                logger.warning(
                    "current_hero — przegląd nieudany (runda %s/%s)",
                    round_n,
                    _CURRENT_HERO_ROUNDS,
                )
                continue

            nick = _read_nick()
            if not nick:
                logger.warning(
                    "current_hero — pusty nick OCR (runda %s/%s)",
                    round_n,
                    _CURRENT_HERO_ROUNDS,
                )
                continue

            matched = _hero_by_nick(self.heroes, nick)
            if matched is None:
                for hero in self.heroes:
                    hero.logged_in = False
                logger.warning(
                    "current_hero — nick %r nie ma na whitelist — swap",
                    nick,
                )
                return None

            hero_id = _clean(get_text(_HERO_ID_REGION, _HERO_ID_ALLOW))
            alliance = _parse_alliance(get_text(_ALLIANCE_REGION, _ALLIANCE_ALLOW))
            pdw, pdw_max = _parse_pdw(get_text(_PDW_REGION, _PDW_ALLOW))

            for hero in self.heroes:
                hero.logged_in = hero is matched
            matched.hero_id = hero_id or None
            matched.alliance = alliance
            matched.pdw = pdw
            matched.pdw_max = pdw_max
            self._miss_streak = 0
            logger.info(
                "zalogowano %s uid=%s hero_id=%s alliance=%s pdw=%s/%s%s",
                matched.nick,
                matched.uid,
                matched.hero_id,
                matched.alliance,
                matched.pdw,
                matched.pdw_max,
                "" if matched.enabled else " (wyłączony w panelu)",
            )
            return True

        for hero in self.heroes:
            hero.logged_in = False
        self._miss_streak += 1
        logger.error("nie wykryto bohatera (%s/%s)", self._miss_streak, 3)
        if self._miss_streak >= 3:
            logger.error(
                "przekroczono limit %s nieudanych wykryć bohatera — zatrzymuję bota",
                3,
            )
            request_stop()
        return False

    def _go_to_hero_review(self) -> bool:
        """
        Ekran przeglądu: widać setting_button (bez klikania).

        Najpierw in_game, potem Esc aż pojawi się kółko. True = widać przycisk.
        """
        if not in_game():
            logger.error("nie jesteśmy w grze — nie można otworzyć przeglądu bohatera")
            return False

        if find_on_screen(_SETTING_BUTTON, timeout=_HERO_REVIEW_SEARCH_TIMEOUT):
            return True

        for attempt in range(_HERO_REVIEW_MAX_ESC):
            activate_window("game")
            press_key("esc")
            stop_sleep(random.uniform(*_HERO_REVIEW_ESC_DELAY))
            if find_on_screen(_SETTING_BUTTON, timeout=_HERO_REVIEW_SEARCH_TIMEOUT):
                return True

        logger.error(
            "current_hero — brak setting_button.png po %s× Esc",
            _HERO_REVIEW_MAX_ESC,
        )
        return False


def _read_nick() -> str:
    """OCR nicku: lewy górny stały, prawy bok = przycisk kopiuj (nick_copy.png)."""
    left, top, max_w, height = _NICK_MAX
    copy_rect = locate_template(
        _NICK_COPY,
        _DETECT_THRESHOLD,
        region=(left, top, max_w + 40, height),
    )
    if copy_rect is None:
        logger.warning("current_hero — brak nick_copy.png, OCR na max regionie nicku")
        region = _NICK_MAX
    else:
        copy_x = copy_rect[0]
        width = max(8, min(max_w, copy_x - left))
        region = (left, top, width, height)
    return _clean(get_text(region, _NICK_ALLOW))


def _hero_by_nick(heroes: list[Hero], nick: str) -> Hero | None:
    """Znajdź hero po nicku (dokładny → wielkość liter → fold_nick)."""
    for hero in heroes:
        if hero.nick == nick:
            return hero
    folded = nick.casefold()
    for hero in heroes:
        if hero.nick.casefold() == folded:
            return hero
    ocr_fold = fold_nick(nick)
    for hero in heroes:
        if fold_nick(hero.nick) == ocr_fold:
            return hero
    return None


def _parse_alliance(raw: str | None) -> str | None:
    """Nazwa sojuszu, 'brak' przy '-', None gdy OCR nic nie dał."""
    text = _clean(raw)
    if not text:
        return None
    if text in ("-", "—", "–"):
        return NO_ALLIANCE
    return text


def _parse_pdw(raw: str | None) -> tuple[int | None, int | None]:
    """'1480/1480' → (1480, 1480). Lewa = aktualne, prawa = max."""
    text = (raw or "").replace(" ", "")
    if "/" in text:
        left, right = text.split("/", 1)
    else:
        left, right = text, ""
    return _digits_to_int(left), _digits_to_int(right)


def _digits_to_int(raw: str) -> int | None:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _clean(raw: str | None) -> str:
    return (raw or "").strip()

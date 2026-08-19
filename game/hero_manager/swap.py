"""
Zamiana postaci i konta.

To kawałek HeroManager — osobny plik, żeby hero_manager.py nie puchł.
"""

from __future__ import annotations

import ctypes
import random
import sys
from difflib import SequenceMatcher
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import click_region, find_and_click, find_on_screen, get_text
from input.engine.mouse import move_to
from log import logger
from state.stop import sleep as stop_sleep

from ..navigation import go_to_setting
from .hero import Hero, fold_nick

# coord_picker 1920×1080 — wyrównane kolumny/wiersze (lewa 536×318, prawa 1257×285).
_SWAP_NICK_SLOTS: tuple[tuple[int, int, int, int], ...] = (
    (536, 376, 318, 30),
    (1257, 376, 285, 30),
    (536, 486, 318, 30),
    (1257, 486, 285, 30),
    (536, 596, 318, 30),
)
# coord_picker 1920×1080 — cała linia: „UID: 12746304 | 6 min temu”.
_ACCOUNT_UID_SLOTS: tuple[tuple[int, int, int, int], ...] = (
    (800, 570, 280, 17),
    (800, 628, 280, 17),
    (800, 687, 280, 17),
)
_NICK_ALLOW = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-[]"
# Litery zostają (UID, min, temu); | : spacja . — żeby kreska przeżyła OCR.
_UID_SLOT_ALLOW = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789|: .-"
)
# Poniżej tego OCR jest za daleko od kandydata — nie klikamy w ciemno.
_MIN_SIMILARITY = 0.75


class HeroSwap:
    """Metody HeroManager: swap_hero i account_swap."""

    def swap_hero(self) -> bool | None:
        """
        Zamień postać, gdy są nieodwiedzeni.

        True — swap OK, None — brak kogo odwiedzić / obcy nick bez naszych w slotach, False — błąd UI.
        OCR nicków w 5 slotach: najpierw 100%, potem najbardziej podobny. Cel zapisuje się
        do sprawdzenia w current_hero (pomyłka → wyłączenie celu).
        """
        self._swap_target = None
        confirm = _ROOT / "templates" / "navigation" / "hero_swap_confirm.png"
        if not confirm.is_file():
            logger.error("swap_hero — brak %s", confirm)
            return False

        uid = self._current_uid()
        candidates = [
            hero
            for hero in self.heroes
            if hero.enabled and not hero.visited and (uid is None or hero.uid == uid)
        ]
        if not candidates:
            return None

        if not _open_hero_swap_menu(
            "nie udało się potwierdzić menu hero swap — brak in_hero_swap_menu.png po %s s"
        ):
            return False

        hits: list[tuple[Hero, tuple[int, int, int, int]]] = []
        seen_nicks: set[str] = set()
        slot_reads: list[tuple[tuple[int, int, int, int], str]] = []
        for slot in _SWAP_NICK_SLOTS:
            raw = get_text(slot, _NICK_ALLOW)
            nick = _nick_from_swap_ocr(raw)
            slot_reads.append((slot, nick))
            hero = _match_candidate(candidates, nick) if nick else None
            if hero is None or hero.nick in seen_nicks:
                continue
            seen_nicks.add(hero.nick)
            hits.append((hero, slot))

        if not hits:
            fuzzy = _best_similar_hit(slot_reads, candidates)
            if fuzzy is None:
                if uid is None:
                    return None
                logger.error(
                    "swap_hero — żaden slot nie pasuje do nieodwiedzonych %s (uid %s)",
                    [hero.nick for hero in candidates],
                    uid,
                )
                return False
            hero, slot, _, _ = fuzzy
            hits.append((hero, slot))

        hero, slot = random.choice(hits)
        click_region(*slot, margin=0.15)
        stop_sleep(random.uniform(0.7, 1.2))
        if find_and_click(confirm, timeout=30.0):
            self._swap_target = hero.nick
            return True

        logger.error("swap_hero — kliknięto %s, ale brak potwierdzenia", hero.nick)
        return False

    def account_swap(self) -> bool | None:
        """
        Zmień konto, gdy bieżące nie ma już nieodwiedzonych hero,
        a inne uid jeszcze mają.

        True — OK, None — brak innych kont, False — błąd.
        Wejście: hero_swap_menu → kroki UI → OCR uid w slotach.
        """
        self._swap_target = None
        if not self._account_swap_enabled:
            return None

        current = self._current_uid()
        # Nieznane konto (obcy nick) — szukamy dowolnego uid z nieodwiedzonymi.
        other_uids = sorted(
            {
                hero.uid
                for hero in self.heroes
                if hero.enabled
                and not hero.visited
                and (current is None or hero.uid != current)
            }
        )
        if not other_uids:
            return None

        if not _open_hero_swap_menu(
            "account_swap — brak in_hero_swap_menu.png po %s s"
        ):
            return False

        # Kroki account swap z hero_swap_menu (coord_picker 1920×1080).
        click_region(456, 199, 632, 60, margin=0.15)
        stop_sleep(random.uniform(3.0, 4.7))
        click_region(814, 679, 296, 30, margin=0.15)
        stop_sleep(random.uniform(3.0, 4.7))
        click_region(808, 500, 299, 28, margin=0.15)
        stop_sleep(random.uniform(0.5, 1.0))

        # OCR slotów → lewa strona „|” = uid → klik → START.
        clicked_uid: str | None = None
        for slot in _ACCOUNT_UID_SLOTS:
            raw = get_text(slot, _UID_SLOT_ALLOW, contrast=True)
            matched = _uid_in_ocr(raw, other_uids)
            if matched is None:
                continue
            click_region(*slot, margin=0.15)
            stop_sleep(random.uniform(0.5, 1.0))
            clicked_uid = matched
            break

        if clicked_uid is None:
            logger.error("account_swap — nie znaleziono w slotach żadnego z: %s", ", ".join(other_uids))
            return False

        # Odsuń kursor w losową krawędź — nie zasłaniał acc_swap_confirm.
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        margin = random.randint(8, 40)
        edge = random.choice(("top", "bottom", "left", "right"))
        if edge == "top":
            mx, my = random.randint(margin, max(margin, sw - margin)), margin
        elif edge == "bottom":
            mx, my = random.randint(margin, max(margin, sw - margin)), sh - margin
        elif edge == "left":
            mx, my = margin, random.randint(margin, max(margin, sh - margin))
        else:
            mx, my = sw - margin, random.randint(margin, max(margin, sh - margin))
        move_to(mx, my)

        confirm = _ROOT / "templates" / "navigation" / "acc_swap_confirm.png"
        if not find_and_click(confirm, timeout=30.0):
            logger.error("account_swap — brak / nie kliknięto acc_swap_confirm.png")
            return False

        return True


def _open_hero_swap_menu(missing_menu_log: str) -> bool:
    """Ustawienia → klik regionu menu swap → czekaj na in_hero_swap_menu.png."""
    if not go_to_setting():
        return False

    # Region menu hero swap (coord_picker 1920×1080).
    click_region(51, 589, 272, 62, margin=0.15)
    stop_sleep(random.uniform(3.0, 4.7))

    menu = _ROOT / "templates" / "navigation" / "in_hero_swap_menu.png"
    if not find_on_screen(menu, timeout=30.0):
        logger.error(missing_menu_log, 30.0)
        return False
    return True


def _nick_from_swap_ocr(raw: str | None) -> str:
    """Z OCR slotu: '[sojusz]nick' → sam nick. Pusty string gdy nic nie ma."""
    text = (raw or "").strip()
    if text.startswith("["):
        close = text.find("]")
        if close != -1:
            text = text[close + 1 :].strip()
    return text


def _match_candidate(candidates: list[Hero], nick: str) -> Hero | None:
    """Dopasuj odczytany nick do nieodwiedzonego hero (bez wielkości liter)."""
    for hero in candidates:
        if hero.nick == nick:
            return hero
    folded = nick.casefold()
    for hero in candidates:
        if hero.nick.casefold() == folded:
            return hero
    return None


def _nick_similarity(ocr_nick: str, hero_nick: str) -> float:
    """0–1: zwykłe podobieństwo albo po złożeniu 1/l/I — bierzemy lepsze."""
    raw = SequenceMatcher(None, ocr_nick.casefold(), hero_nick.casefold()).ratio()
    folded = SequenceMatcher(None, fold_nick(ocr_nick), fold_nick(hero_nick)).ratio()
    return max(raw, folded)


def _best_similar_hit(
    slot_reads: list[tuple[tuple[int, int, int, int], str]],
    candidates: list[Hero],
) -> tuple[Hero, tuple[int, int, int, int], float, str] | None:
    """Najbardziej podobny OCR do kandydata. None gdy pusto albo za słabe."""
    best: tuple[float, Hero, tuple[int, int, int, int], str] | None = None
    for slot, nick in slot_reads:
        if not nick:
            continue
        for hero in candidates:
            score = _nick_similarity(nick, hero.nick)
            if best is None or score > best[0]:
                best = (score, hero, slot, nick)
    if best is None or best[0] < _MIN_SIMILARITY:
        return None
    return best[1], best[2], best[0], best[3]


def _uid_from_slot_ocr(raw: str | None) -> str:
    """Linia 'UID: 12746304 | 6 min temu' → '12746304'. Prawy bok (czas) olewamy."""
    text = (raw or "").strip()
    if "|" in text:
        text = text.split("|", 1)[0]
    return "".join(ch for ch in text if ch.isdigit())


def _uid_in_ocr(raw: str | None, uids: list[str]) -> str | None:
    """Trafienie = szukany uid jest fragmentem odczytanych cyfr. Kilka pasuje → najdłuższy."""
    parsed = _uid_from_slot_ocr(raw)
    if not parsed:
        return None
    hits = [uid for uid in uids if uid and uid in parsed]
    if not hits:
        return None
    return max(hits, key=len)

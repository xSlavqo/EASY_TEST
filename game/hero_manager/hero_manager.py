"""
Zarządzanie postaciami — wykrywanie zalogowanego, visited w cyklu, zamiana w menu.
"""

from __future__ import annotations

import ctypes
import random
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

# Pakiet jest w game/hero_manager/ → root projektu = 3 poziomy wyżej.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from input import click_region, find_and_click, find_on_screen, get_text, match_score, screenshot
from input.engine.mouse import move_to
from log import logger
from state.keys import HEROES_VISITED
from state.stop import check_stop, request_stop, sleep as stop_sleep
from state.store import INFO_PATH, get_data, save_data

from ..navigation import go_to_setting
from ..view_detector import in_game
from .hero import Hero

# Brak matcha main.png → in_game (Esc/overlay) → znowu awatary. Max rund.
_CURRENT_HERO_ROUNDS = 3
_AVATAR_MATCH_THRESHOLD = 0.99


class HeroManager:
    """Bohaterowie z dysku + operacje na nich."""

    def __init__(self, heroes: list[Hero]) -> None:
        self.heroes = heroes
        self._miss_streak = 0
        # False po 2× fail account_swap — do restartu procesu bota.
        self._account_swap_enabled = True
        # Przywróć visited z info.json (przeżywa restart procesu).
        raw = get_data(INFO_PATH, HEROES_VISITED, default=[])
        keys = {str(x) for x in raw} if isinstance(raw, list) else set()
        for hero in self.heroes:
            hero.visited = f"{hero.email}/{hero.id}" in keys
        if keys:
            logger.info("visited z dysku: %s", ", ".join(sorted(keys)))

    @property
    def visited_ids(self) -> list[str]:
        return sorted(hero.id for hero in self.heroes if hero.visited)

    def _current_email(self) -> str | None:
        """Email konta zalogowanego bohatera (z main.png → Hero.email)."""
        for hero in self.heroes:
            if hero.logged_in:
                return hero.email
        return None

    def disable_account_swap(self) -> None:
        """Wyłącz zamianę kont do ponownego uruchomienia bota."""
        self._account_swap_enabled = False
        logger.error("account_swap wyłączony — pomijany do ponownego uruchomienia bota")

    def current_hero(
        self,
        *,
        timeout: float = 60.0,
        poll: float = 5.0,
    ) -> bool:
        """
        in_game → match main.png → ustaw logged_in.

        Brak awatara → znowu in_game (zamyka popup/ustawienia) → znowu match.
        Max _CURRENT_HERO_ROUNDS rund. Kolizja ≥2 main.png → stop bota.
        """
        # timeout/poll zostawione w sygnaturze — stare wywołania; logika to rundy in_game.
        _ = timeout, poll
        logger.info(
            "current_hero START rundy=%s heroes=%s",
            _CURRENT_HERO_ROUNDS,
            len(self.heroes),
        )

        for round_n in range(1, _CURRENT_HERO_ROUNDS + 1):
            check_stop()
            logger.info("current_hero runda %s/%s → in_game()", round_n, _CURRENT_HERO_ROUNDS)
            if not in_game():
                logger.error(
                    "current_hero — in_game nieudany (runda %s/%s)",
                    round_n,
                    _CURRENT_HERO_ROUNDS,
                )
                # Brak świata gry — kolejna runda i tak zacznie od in_game.
                continue

            logger.info("current_hero runda %s/%s → match main.png", round_n, _CURRENT_HERO_ROUNDS)
            matches: list[tuple[Hero, float]] = []
            try:
                screen = screenshot()
                for hero in self.heroes:
                    score = match_score(screen, hero.main)
                    if score >= _AVATAR_MATCH_THRESHOLD:
                        matches.append((hero, score))
                        logger.info(
                            "current_hero runda %s HIT %s/%s score=%.4f",
                            round_n,
                            hero.email,
                            hero.id,
                            score,
                        )
            except Exception as exc:
                matches = []
                logger.info("current_hero runda %s wyjątek przy matchu: %s", round_n, exc)

            logger.info("current_hero runda %s matches=%s", round_n, len(matches))

            if len(matches) > 1:
                for hero in self.heroes:
                    hero.logged_in = False
                labels = [
                    f"{hero.id} @ {hero.email} (score={score:.4f})"
                    for hero, score in sorted(matches, key=lambda m: -m[1])
                ]
                emails = sorted({hero.email for hero, _ in matches})
                logger.error(
                    "KOLIZJA AWATARÓW main.png — na ekranie pasuje więcej niż jeden bohater: %s. "
                    "Konta z pokrywającymi się awatarami: %s. Ustaw inny main.png dla tych postaci "
                    "(nie mogą wyglądać tak samo / dawać tego samego matcha).",
                    "; ".join(labels),
                    ", ".join(emails),
                )
                request_stop()
                return False

            if len(matches) == 1:
                detected, score = matches[0]
                for hero in self.heroes:
                    hero.logged_in = hero is detected
                self._miss_streak = 0
                # TODO: sprawdź w jakim sojuszu jest hero (O / OCR nazwy) i przypisz
                # detected.alliance = "..." albo None gdy brak sojuszu (no_ally).
                # Na razie zostaje stałe "MZ2" z __init__.
                logger.info(
                    "zalogowano %s (%s) alliance=%s score=%.4f",
                    detected.id,
                    detected.email,
                    detected.alliance,
                    score,
                )
                logger.info("current_hero OK (runda %s)", round_n)
                return True

            # Brak awatarów → kolejna runda zaczyna się od in_game (Esc/overlay w detect_view).
            logger.info(
                "current_hero runda %s/%s — brak awatarów → następna runda od in_game",
                round_n,
                _CURRENT_HERO_ROUNDS,
            )

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
        logger.info("current_hero FAIL — brak awatara po %s rundach", _CURRENT_HERO_ROUNDS)
        return False

    def hero_visited(self) -> None:
        """Oznacz zalogowanego bohatera jako odwiedzonego (+ zapis do info.json)."""
        for hero in self.heroes:
            if hero.logged_in:
                hero.visited = True
                save_data(
                    INFO_PATH,
                    HEROES_VISITED,
                    sorted(f"{h.email}/{h.id}" for h in self.heroes if h.visited),
                )
                return
        logger.error("hero_visited — brak zalogowanego bohatera")

    def reset_all_hero_visited(self) -> None:
        """Wyzeruj visited u wszystkich — po zakończeniu cyklu (+ info.json)."""
        for hero in self.heroes:
            hero.visited = False
        save_data(INFO_PATH, HEROES_VISITED, [])

    def is_visited(self) -> bool:
        """Czy zalogowany hero jest już oznaczony jako visited w tym cyklu."""
        for hero in self.heroes:
            if hero.logged_in:
                return hero.visited
        return False

    def is_in_alliance(self) -> bool:
        """Czy zalogowany hero ma przypisany sojusz."""
        for hero in self.heroes:
            if hero.logged_in:
                return bool(hero.alliance)
        return False

    def swap_hero(self) -> bool | None:
        """
        Zamień postać, gdy są nieodwiedzeni.

        True — swap OK, None — brak kogo odwiedzić (koniec cyklu), False — błąd.
        """
        confirm = _ROOT / "templates" / "navigation" / "hero_swap_confirm.png"
        if not confirm.is_file():
            logger.error("swap_hero — brak %s", confirm)
            return False

        email = self._current_email()
        if email is None:
            logger.error("swap_hero — brak zalogowanego bohatera (nieznane konto)")
            return False

        candidates = [
            hero
            for hero in self.heroes
            if not hero.visited and hero.email == email
        ]
        if not candidates:
            logger.info("swap_hero — brak nieodwiedzonych na %s (visited: %s)", email, self.visited_ids)
            return None

        if not go_to_setting():
            return False

        # Region menu hero swap (coord_picker 1920×1080).
        click_region(51, 589, 272, 62, margin=0.15)
        stop_sleep(random.uniform(3.0, 4.7))

        menu = _ROOT / "templates" / "navigation" / "in_hero_swap_menu.png"
        if not find_on_screen(menu, timeout=30.0):
            logger.error("nie udało się potwierdzić menu hero swap — brak in_hero_swap_menu.png po %s s", 30.0)
            return False

        for hero in random.sample(candidates, len(candidates)):
            if hero.swap is None:
                continue

            # swap.png = landmark — klikamy w prawo, we wpis bohatera obok awatara.
            if not find_and_click(hero.swap, timeout=2.0, offset_x=random.randint(150, 250)):
                continue

            stop_sleep(random.uniform(3.0, 4.7))
            if find_and_click(confirm, timeout=30.0):
                return True

            logger.error("swap_hero — kliknięto %s (%s), ale brak potwierdzenia", hero.id, hero.email)
            return False

        remaining = [
            hero.id
            for hero in self.heroes
            if not hero.visited and hero.email == email
        ]
        logger.info("swap_hero — brak widocznych nieodwiedzonych na %s (visited: %s, pozostali: %s)", email, self.visited_ids, remaining)
        return False

    def account_swap(self) -> bool | None:
        """
        Zmień konto, gdy bieżące nie ma już nieodwiedzonych hero,
        a inne emaile jeszcze mają.

        True — OK, None — brak innych kont, False — błąd.
        Wejście: hero_swap_menu → kroki UI → OCR emaili w slotach.
        """
        if not self._account_swap_enabled:
            logger.info("account_swap — wyłączony (wcześniejszy błąd), koniec zamiany kont")
            return None

        current = self._current_email()
        if current is None:
            logger.error("account_swap — brak zalogowanego bohatera (nieznane konto)")
            return False

        # Inne konta z ≥1 nieodwiedzonego hero.
        other_emails = sorted(
            {
                hero.email
                for hero in self.heroes
                if not hero.visited and hero.email != current
            }
        )
        if not other_emails:
            logger.info("account_swap — brak innych kont z nieodwiedzonych (bieżące: %s)", current)
            return None

        if not go_to_setting():
            return False

        # Region menu hero swap (coord_picker 1920×1080).
        click_region(51, 589, 272, 62, margin=0.15)
        stop_sleep(random.uniform(3.0, 4.7))

        menu = _ROOT / "templates" / "navigation" / "in_hero_swap_menu.png"
        if not find_on_screen(menu, timeout=30.0):
            logger.error("account_swap — brak in_hero_swap_menu.png po %s s", 30.0)
            return False

        # Kroki account swap z hero_swap_menu (coord_picker 1920×1080).
        click_region(456, 199, 632, 60, margin=0.15)
        stop_sleep(random.uniform(3.0, 4.7))
        click_region(814, 679, 296, 30, margin=0.15)
        stop_sleep(random.uniform(3.0, 4.7))
        click_region(808, 500, 299, 28, margin=0.15)
        stop_sleep(random.uniform(0.5, 1.0))

        # OCR slotów → klik nieodwiedzonego emaila → START (acc_swap_confirm).
        email_re = re.compile(r"[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}")
        allowlist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@._-+"
        slots = (
            (840, 552, 210, 19),  # slot 1
            (840, 610, 212, 19),  # slot 2
            (839, 668, 222, 20),  # slot 3
        )
        target_by_key = {email.lower().replace(" ", ""): email for email in other_emails}
        targets = set(target_by_key)
        clicked_email: str | None = None
        for slot in slots:
            raw = (get_text(slot, allowlist) or "").strip().lower().replace(" ", "")
            if not raw:
                continue
            m = email_re.search(raw)
            ocr_email = m.group(0) if m else raw

            matched_key: str | None = None
            best_ratio = 0.0
            for email in targets:
                if email == ocr_email or email in ocr_email or ocr_email in email:
                    matched_key = email
                    best_ratio = 1.0
                    break
                ratio = SequenceMatcher(None, email, ocr_email).ratio()
                local_t, _, _ = email.partition("@")
                local_o, _, _ = ocr_email.partition("@")
                if local_t and local_o:
                    ratio = max(ratio, SequenceMatcher(None, local_t, local_o).ratio())
                if ratio >= 0.82 and ratio > best_ratio:
                    best_ratio = ratio
                    matched_key = email

            if matched_key is None:
                continue

            matched = target_by_key[matched_key]
            click_region(*slot, margin=0.15)
            stop_sleep(random.uniform(0.5, 1.0))
            clicked_email = matched
            break

        if clicked_email is None:
            logger.error("account_swap — nie znaleziono w slotach żadnego z: %s", ", ".join(other_emails))
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


_heroes: list[Hero] = []
_heroes_dir = _ROOT / "templates" / "heroes"
if _heroes_dir.is_dir():
    # templates/heroes/<email>/<hero_id>/{main,swap}.png — email przypisany do main.png
    for _account_dir in sorted(_heroes_dir.iterdir()):
        if not _account_dir.is_dir():
            continue
        for _hero_dir in sorted(_account_dir.iterdir()):
            if not _hero_dir.is_dir():
                continue
            _main = _hero_dir / "main.png"
            if not _main.is_file():
                continue
            _swap_path = _hero_dir / "swap.png"
            _swap = _swap_path if _swap_path.is_file() else None
            if _swap is None:
                logger.warning("brak swap.png dla %s/%s — pomijany przy zamianie", _account_dir.name, _hero_dir.name)
            _heroes.append(Hero(_account_dir.name, _hero_dir.name, _main, _swap))

manager = HeroManager(_heroes)

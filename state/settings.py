"""
Ustawienia z panelu WWW — data/config.json.

Użycie: settings.gather_rss_enabled  /  settings.cycle_interval_min_h = 4.0
Każdy odczyt/zapis idzie do pliku (przez store).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import get_data, save_data

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT / "data" / "config.json"

# Domyślne wartości, gdy klucza nie ma w pliku.
_DEFAULTS: dict[str, Any] = {
    "close_game_after_cycle": False,
    "alliance_rss_enabled": True,
    "alliance_pit_enabled": True,
    "gather_buff_enabled": True,
    "gather_rss_enabled": True,
    "scount_sentry_post_enabled": True,
    "gather_rss_gold": True,
    "gather_rss_wood": True,
    "gather_rss_ore": True,
    "gather_rss_mana": True,
    # Harmonogram (godziny) — cykl bota i cooldowny tasków.
    "cycle_interval_min_h": 4.0,
    "cycle_interval_max_h": 5.0,
    "alliance_rss_cooldown_h": 10.0,
    "ssp_cooldown_h": 14.0,
    # Opóźnienia (sekundy) po swapie konta / przed zamknięciem gry.
    "relogin_focus_delay_sec": 15.0,
    "close_game_delay_sec": 30.0,
}


class Settings:
    """Jedna globalna fasada: settings.nazwa czyta/zapisuje config.json."""

    def __getattr__(self, name: str) -> Any:
        """Odczyt: settings.xyz → wartość z JSON albo z _DEFAULTS."""
        if name.startswith("_") or name not in _DEFAULTS:
            raise AttributeError(f"nieznane ustawienie: {name}")
        return get_data(CONFIG_PATH, name, _DEFAULTS[name])

    def __setattr__(self, name: str, value: Any) -> None:
        """Zapis: settings.xyz = v → do config.json (albo zwykłe pole z _)."""
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        if name not in _DEFAULTS:
            raise AttributeError(f"nieznane ustawienie: {name}")
        save_data(CONFIG_PATH, name, value)


# Jedyna instancja używana w całym projekcie.
settings = Settings()

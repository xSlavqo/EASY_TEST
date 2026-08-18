"""Karta ustawień — checkboxy, harmonogram, opóźnienia."""

from __future__ import annotations

from nicegui import ui

from state.settings import settings

# (klucz w config.json, etykieta w panelu)
_CHECKS = (
    ("close_game_after_cycle", "Zamykaj grę po cyklu"),
    ("alliance_rss_enabled", "Odbierz surowce sojuszu"),
    ("alliance_pit_enabled", "Centrum zasobów przymierza"),
    ("scount_sentry_post_enabled", "Sentry Post (próby scouta)"),
    ("gather_rss_enabled", "Zbieranie RSS"),
    ("gather_rss_gold", "RSS: złoto"),
    ("gather_rss_wood", "RSS: drewno"),
    ("gather_rss_ore", "RSS: ruda"),
)

_GATHER_RSS_LEVEL_MIN = 1
_GATHER_RSS_LEVEL_MAX = 10

# Limity pól liczbowych w panelu (godziny / sekundy).
_HOURS_MIN = 0.1
_HOURS_MAX = 168.0  # tydzień
_DELAY_SEC_MIN = 0.0
_DELAY_SEC_MAX = 600.0


def _save_float_setting(key: str, raw: object, *, lo: float, hi: float) -> None:
    """Zapisz liczbę z pola UI do settings (z ograniczeniem zakresu)."""
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return
    setattr(settings, key, max(lo, min(hi, value)))


def _clamp_cycle_interval_pair() -> None:
    """Upewnij się, że min cyklu ≤ max (po edycji jednego z pól)."""
    lo = float(settings.cycle_interval_min_h)
    hi = float(settings.cycle_interval_max_h)
    if hi < lo:
        settings.cycle_interval_max_h = lo


def build_settings_panel() -> None:
    """Prawa karta: przełączniki tasków i liczby z config.json."""
    with ui.card().classes(
        "w-full md:w-96 shrink-0 md:h-full overflow-auto bg-[#383838]"
    ):
        ui.label("Ustawienia").classes("text-subtitle1")
        for key, label in _CHECKS:

            def _on_toggle(e, k: str = key) -> None:
                setattr(settings, k, bool(e.value))

            ui.checkbox(
                label,
                value=bool(getattr(settings, key)),
                on_change=_on_toggle,
            )

        with ui.row().classes("items-center gap-2 flex-wrap mt-2"):
            ui.label("RSS: poziom")

            def _on_level(e) -> None:
                try:
                    level = int(e.value)
                except (TypeError, ValueError):
                    return
                level = max(
                    _GATHER_RSS_LEVEL_MIN,
                    min(_GATHER_RSS_LEVEL_MAX, level),
                )
                settings.gather_rss_level = level

            ui.number(
                value=int(settings.gather_rss_level),
                min=_GATHER_RSS_LEVEL_MIN,
                max=_GATHER_RSS_LEVEL_MAX,
                step=1,
                on_change=_on_level,
            ).props("dense outlined").classes("w-24")

        # Harmonogram — godziny (bot czyta przy następnym schedule).
        ui.separator().classes("my-3")
        ui.label("Harmonogram").classes("text-subtitle2")

        def _on_cycle_min(e) -> None:
            _save_float_setting(
                "cycle_interval_min_h",
                e.value,
                lo=_HOURS_MIN,
                hi=_HOURS_MAX,
            )
            _clamp_cycle_interval_pair()

        def _on_cycle_max(e) -> None:
            _save_float_setting(
                "cycle_interval_max_h",
                e.value,
                lo=_HOURS_MIN,
                hi=_HOURS_MAX,
            )
            _clamp_cycle_interval_pair()

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("cykl min (h)")
            ui.number(
                value=float(settings.cycle_interval_min_h),
                min=_HOURS_MIN,
                max=_HOURS_MAX,
                step=0.5,
                on_change=_on_cycle_min,
            ).props("dense outlined").classes("w-24")

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("cykl max (h)")
            ui.number(
                value=float(settings.cycle_interval_max_h),
                min=_HOURS_MIN,
                max=_HOURS_MAX,
                step=0.5,
                on_change=_on_cycle_max,
            ).props("dense outlined").classes("w-24")

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("cooldown ally RSS (h)")

            def _on_ally_cd(e) -> None:
                _save_float_setting(
                    "alliance_rss_cooldown_h",
                    e.value,
                    lo=_HOURS_MIN,
                    hi=_HOURS_MAX,
                )

            ui.number(
                value=float(settings.alliance_rss_cooldown_h),
                min=_HOURS_MIN,
                max=_HOURS_MAX,
                step=0.5,
                on_change=_on_ally_cd,
            ).props("dense outlined").classes("w-24")

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("cooldown SSP (h)")

            def _on_ssp_cd(e) -> None:
                _save_float_setting(
                    "ssp_cooldown_h",
                    e.value,
                    lo=_HOURS_MIN,
                    hi=_HOURS_MAX,
                )

            ui.number(
                value=float(settings.ssp_cooldown_h),
                min=_HOURS_MIN,
                max=_HOURS_MAX,
                step=0.5,
                on_change=_on_ssp_cd,
            ).props("dense outlined").classes("w-24")

        # Opóźnienia krótkie — sekundy.
        ui.separator().classes("my-3")
        ui.label("Opóźnienia").classes("text-subtitle2")

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("po swapie konta (s)")

            def _on_relogin(e) -> None:
                _save_float_setting(
                    "relogin_focus_delay_sec",
                    e.value,
                    lo=_DELAY_SEC_MIN,
                    hi=_DELAY_SEC_MAX,
                )

            ui.number(
                value=float(settings.relogin_focus_delay_sec),
                min=_DELAY_SEC_MIN,
                max=_DELAY_SEC_MAX,
                step=1,
                on_change=_on_relogin,
            ).props("dense outlined").classes("w-24")

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.label("przed zamknięciem gry (s)")

            def _on_close_delay(e) -> None:
                _save_float_setting(
                    "close_game_delay_sec",
                    e.value,
                    lo=_DELAY_SEC_MIN,
                    hi=_DELAY_SEC_MAX,
                )

            ui.number(
                value=float(settings.close_game_delay_sec),
                min=_DELAY_SEC_MIN,
                max=_DELAY_SEC_MAX,
                step=1,
                on_change=_on_close_delay,
            ).props("dense outlined").classes("w-24")

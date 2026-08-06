"""Logger bota — INFO, WARNING i ERROR, plik (+ UI / Discord przez attach_handler)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_FILE = _LOG_DIR / "bot.log"
_SCREEN_DIR = _LOG_DIR / "screens"

_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class BotLogger:
    """Opakowanie logging.Logger — info (kamienie milowe), warning, error."""

    def __init__(self) -> None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("easy_test")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._error_screenshot_hooks: list[Callable[[Path], None]] = []

        if not self._logger.handlers:
            formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

            file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def attach_handler(self, handler: logging.Handler) -> None:
        """Dopina dodatkowe wyjście (np. terminal w UI, Discord) — bezpiecznie po starcie."""
        if handler.level == logging.NOTSET:
            handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
        self._logger.addHandler(handler)

    def on_error_screenshot(self, hook: Callable[[Path], None]) -> None:
        """Callback po zapisie screena z logger.error (np. wysyłka na Discord)."""
        self._error_screenshot_hooks.append(hook)

    def info(self, message: str, *args: object) -> None:
        """Ważny etap — sukces, zaplanowane uruchomienie itp."""
        self._logger.info(message, *args)

    def warning(self, message: str, *args: object) -> None:
        """Coś się nie udało, ale można iść dalej."""
        self._logger.warning(message, *args)

    def error(self, message: str, *args: object) -> None:
        """Błąd krytyczny — log + zrzut ekranu do logs/screens/ (+ hooki, np. Discord)."""
        self._logger.error(message, *args)
        # Zrzut poza głównym logiem — awaria screena nie może zabić errora.
        try:
            import cv2
            from input.engine.vision import screenshot

            _SCREEN_DIR.mkdir(parents=True, exist_ok=True)
            path = _SCREEN_DIR / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            if cv2.imwrite(str(path), screenshot()):
                self._logger.error("screenshot: %s", path)
                for hook in self._error_screenshot_hooks:
                    try:
                        hook(path)
                    except Exception:
                        pass
        except Exception:
            pass


logger = BotLogger()

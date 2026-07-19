"""Logger bota — INFO, WARNING i ERROR, plik + konsola."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_FILE = _LOG_DIR / "bot.log"

_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_console_encoding() -> None:
    """UTF-8 w konsoli Windows — StreamHandler loguje na stderr, nie stdout."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


class BotLogger:
    """Opakowanie logging.Logger — info (kamienie milowe), warning, error."""

    def __init__(self) -> None:
        _configure_console_encoding()
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("easy_test")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

            file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

    def attach_handler(self, handler: logging.Handler) -> None:
        """Dopina dodatkowe wyjście (np. terminal w UI) — bezpiecznie po starcie okna."""
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
        self._logger.addHandler(handler)

    def info(self, message: str, *args: object) -> None:
        """Ważny etap — sukces, zaplanowane uruchomienie itp."""
        self._logger.info(message, *args)

    def warning(self, message: str, *args: object) -> None:
        """Coś się nie udało, ale można iść dalej."""
        self._logger.warning(message, *args)

    def error(self, message: str, *args: object) -> None:
        """Błąd krytyczny zatrzymujący logikę."""
        self._logger.error(message, *args)


logger = BotLogger()

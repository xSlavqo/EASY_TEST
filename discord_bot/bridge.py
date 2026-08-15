"""Most Discord — wysyłka logów na kanał (komendy później)."""

from __future__ import annotations

import asyncio
import logging
import queue
import shutil
import threading
from pathlib import Path
from typing import Any

import discord

from log import logger
from state.json_io import load_file

_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _DIR / "config.json"
_EXAMPLE_PATH = _DIR / "config.example.json"

_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "token": "",
    "log_channel_id": 0,
    "min_level": "INFO",
}

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

# str = zwykły log; Path = screen z logger.error
_QueueItem = str | Path

# ERROR dostaje @everyone; screen bez drugiego pingu.
_ALLOW_EVERYONE = discord.AllowedMentions(everyone=True)
_NO_MENTIONS = discord.AllowedMentions.none()

_started = False


def _ensure_config() -> None:
    """Brak config.json → skopiuj szablon z example."""
    if _CONFIG_PATH.is_file():
        return
    if _EXAMPLE_PATH.is_file():
        shutil.copyfile(_EXAMPLE_PATH, _CONFIG_PATH)
        return
    _CONFIG_PATH.write_text(
        '{\n  "enabled": false,\n  "token": "",\n  "log_channel_id": 0,\n  "min_level": "INFO"\n}\n',
        encoding="utf-8",
    )


def _load_config() -> dict[str, Any]:
    _ensure_config()
    raw = load_file(_CONFIG_PATH)
    cfg = dict(_DEFAULTS)
    for key in _DEFAULTS:
        if key in raw:
            cfg[key] = raw[key]
    return cfg


def start_discord_bot() -> bool:
    """Uruchom bota Discord w tle i podepnij handler logów. False = wyłączony / błąd configu."""
    global _started
    if _started:
        return True

    cfg = _load_config()
    if not cfg["enabled"]:
        return False

    token = str(cfg["token"] or "").strip()
    try:
        channel_id = int(cfg["log_channel_id"] or 0)
    except (TypeError, ValueError):
        channel_id = 0

    if not token or channel_id <= 0:
        logger.warning("discord: uzupełnij token i log_channel_id w discord_bot/config.json")
        return False

    min_level = _LEVELS.get(str(cfg["min_level"]).upper(), logging.INFO)
    msg_queue: queue.Queue[_QueueItem] = queue.Queue()

    class _DiscordLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                text = self.format(record)
                # Screen idzie osobno jako plik (hook) — bez dubla ścieżki w tekście.
                if record.levelno >= logging.ERROR and "screenshot:" in text:
                    return
                # Postój / błąd krytyczny — jeden ping @everyone (nie przy screenie).
                if record.levelno >= logging.ERROR:
                    text = f"@everyone\n{text}"
                msg_queue.put_nowait(text[:1900])
            except Exception:
                self.handleError(record)

    def _enqueue_screenshot(path: Path) -> None:
        try:
            msg_queue.put_nowait(path)
        except Exception:
            pass

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except Exception:
                logger.error("discord: nie znaleziono kanału id=%s", channel_id)
                return

        while not client.is_closed():
            try:
                item = msg_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.4)
                continue
            try:
                if isinstance(item, Path):
                    if item.is_file():
                        await channel.send(
                            content="screenshot (error)",
                            file=discord.File(item),
                            allowed_mentions=_NO_MENTIONS,
                        )
                else:
                    mentions = (
                        _ALLOW_EVERYONE
                        if "@everyone" in item
                        else _NO_MENTIONS
                    )
                    await channel.send(item, allowed_mentions=mentions)
            except Exception:
                logger.warning("discord: nie udało się wysłać wiadomości na kanał")

    def _run() -> None:
        try:
            client.run(token, log_handler=None)
        except Exception:
            logger.error("discord: połączenie zerwane lub nieprawidłowy token")

    handler = _DiscordLogHandler()
    handler.setLevel(min_level)
    logger.attach_handler(handler)
    logger.on_error_screenshot(_enqueue_screenshot)

    threading.Thread(target=_run, name="discord-bot", daemon=True).start()
    _started = True
    return True

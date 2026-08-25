"""
Pakiet state — dysk i sterowanie botem.

Pliki (od dołu):
  json_io   — jak czytać/pisać cały plik JSON
  store     — klucz → wartość w JSON (get_data / save_data)
  keys      — nazwy kluczy w info.json
  schedule  — kiedy bot/task może ruszyć
  settings  — config.json (panel WWW)
  stop      — Start/Stop / F9
  task_defs — lista tasków (id + etykiety)
"""

from .keys import BOT
from .schedule import is_due, schedule, sleep_until_due
from .settings import CONFIG_PATH, settings
from .store import INFO_PATH, delete_data, get_data, save_data

__all__ = [
    "BOT",
    "CONFIG_PATH",
    "INFO_PATH",
    "delete_data",
    "get_data",
    "is_due",
    "save_data",
    "schedule",
    "settings",
    "sleep_until_due",
]

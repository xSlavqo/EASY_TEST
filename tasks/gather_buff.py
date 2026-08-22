"""
Zadanie: gather_buff — zbieranie buffów (sojusz / mapa).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def gather_buff() -> bool:
    """True = OK / skip. False = błąd UI (manager wyłącza task u hero)."""
    return True

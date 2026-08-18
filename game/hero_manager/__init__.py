"""Pakiet zarządzania bohaterami — Hero + HeroManager.

Pliki: current_hero.py (wykrywanie), swap.py (zamiana), hero_manager.py (lista / visited).
"""

from .hero import Hero
from .hero_manager import HeroManager, manager

__all__ = ["Hero", "HeroManager", "manager"]

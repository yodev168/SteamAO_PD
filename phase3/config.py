"""
config.py — Phase 3 paths
"""
from pathlib import Path

BASE = Path(__file__).parent
PHASE2 = BASE.parent / "phase2"

MASTER_CSV = PHASE2 / "ao_games_master.csv"
CLEANED_CSV = BASE / "ao_games_cleaned.csv"

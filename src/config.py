"""Paths and constants shared across the pipeline."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH_ROOT = Path(os.environ.get("SH_ROOT", ROOT.parent / "synthetic_hospital-main"))  # Synthetic Hospital repo
DB_PATH = SH_ROOT / "benchmark_v1.3.db"
DATA = ROOT / "data"
RESULTS = ROOT / "results"

SEED = 20260927
MIN_ENCOUNTERS = 5
PILOT_SIZE = 50

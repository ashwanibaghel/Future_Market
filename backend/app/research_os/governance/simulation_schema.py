import os
from typing import Dict, Any
import pyarrow as pa

from app.research_os.governance.dataset_registry import RESEARCH_STORAGE_DIR

SIMULATION_STORAGE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "trade_simulations")

# Phase 8: Trade Simulation Foundation Parquet & Database Schema Definition
TRADE_SIMULATION_SCHEMA = pa.schema([
    ("simulation_id", pa.string()),
    ("strategy_id", pa.string()),
    ("symbol", pa.string()),
    ("entry_time", pa.string()),
    ("exit_time", pa.string()),
    ("entry_price", pa.float64()),
    ("exit_price", pa.float64()),
    ("stop_loss", pa.float64()),
    ("target", pa.float64()),
    ("pnl", pa.float64()),
    ("pnl_percentage", pa.float64()),
    ("max_drawdown", pa.float64()),
    ("reason_for_entry", pa.string()),
    ("reason_for_exit", pa.string()),
    ("actual_market_result", pa.string()),
    ("simulation_result", pa.string()),
    ("created_at", pa.string()),
])


def ensure_simulation_storage_structure() -> str:
    """Ensures trade_simulations storage directory exists."""
    os.makedirs(SIMULATION_STORAGE_DIR, exist_ok=True)
    return SIMULATION_STORAGE_DIR

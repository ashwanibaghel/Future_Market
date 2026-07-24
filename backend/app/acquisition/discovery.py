import os
import csv
import gzip
import sqlite3
import urllib.request
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

logger = logging.getLogger("acquisition.discovery")

ACQUISITION_DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../research_storage/instrument_master"))
INSTRUMENTS_DB_PATH = os.path.join(ACQUISITION_DB_DIR, "instruments.db")


class InstrumentType(str, Enum):
    INDEX = "INDEX"
    EQUITY = "EQUITY"
    ETF = "ETF"
    OPTION_INDEX = "OPTION_INDEX"
    OPTION_EQUITY = "OPTION_EQUITY"


class Exchange(str, Enum):
    BSE_INDEX = "BSE_INDEX"
    NSE_INDEX = "NSE_INDEX"
    BSE_EQ = "BSE_EQ"
    NSE_EQ = "NSE_EQ"
    NSE_FO = "NSE_FO"


@dataclass
class GenericInstrument:
    instrument_key: str
    exchange: str
    trading_symbol: str
    display_name: str
    instrument_type: str
    isin: Optional[str] = None
    tick_size: float = 0.05
    lot_size: int = 1
    underlying_key: Optional[str] = None
    is_active: bool = True


# Default SENSEX 30 Constituent ISIN Catalog
SENSEX_30_ISINS = {
    "RELIANCE": "INE002A01018",
    "TCS": "INE467B01029",
    "HDFCBANK": "INE040A01034",
    "ICICIBANK": "INE090A01021",
    "INFY": "INE009A01021",
    "BHARTIARTL": "INE397D01024",
    "SBIN": "INE062A01020",
    "LT": "INE018A01030",
    "ITC": "INE154A01025",
    "HINDUNILVR": "INE030A01027",
    "AXISBANK": "INE238A01034",
    "KOTAKBANK": "INE237A01028",
    "M&M": "INE101A01026",
    "NTPC": "INE733E01010",
    "TATAMOTORS": "INE155A01022",
    "POWERGRID": "INE752E01010",
    "HCLTECH": "INE860A01027",
    "MARUTI": "INE585B01010",
    "SUNPHARMA": "INE044A01036",
    "TITAN": "INE280A01028",
    "ASIANPAINT": "INE021A01026",
    "TATASTEEL": "INE081A01020",
    "BAJFINANCE": "INE296A01024",
    "ULTRACEMCO": "INE481G01011",
    "NESTLEIND": "INE239A01024",
    "TECHM": "INE669C01036",
    "INDUSINDBK": "INE095A01012",
    "BAJAJFINSV": "INE918I01026",
    "JSWSTEEL": "INE019A01038",
    "ADANIPORTS": "INE742F01042",
}


def init_instruments_db(db_path: str = INSTRUMENTS_DB_PATH) -> sqlite3.Connection:
    """Initializes the relational Instrument Master SQLite database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS instruments_master (
        instrument_key TEXT PRIMARY KEY,
        exchange TEXT NOT NULL,
        trading_symbol TEXT NOT NULL,
        display_name TEXT NOT NULL,
        instrument_type TEXT NOT NULL,
        isin TEXT,
        tick_size REAL DEFAULT 0.05,
        lot_size INTEGER DEFAULT 1,
        underlying_key TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sync_history (
        sync_id TEXT PRIMARY KEY,
        instrument_key TEXT NOT NULL,
        sync_type TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        total_candles_synced INTEGER NOT NULL,
        missing_minutes_detected INTEGER DEFAULT 0,
        sha256_checksum TEXT NOT NULL,
        status TEXT NOT NULL,
        synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(instrument_key) REFERENCES instruments_master(instrument_key)
    );
    """)

    conn.commit()
    return conn


class InstrumentDiscoveryService:
    """Manages instrument master registration, key lookup, and discovery."""

    def __init__(self, db_path: str = INSTRUMENTS_DB_PATH):
        self.db_path = db_path
        self.conn = init_instruments_db(db_path)
        self.seed_phase1_instruments()

    def seed_phase1_instruments(self):
        """Seeds Phase 1 target instruments (SENSEX, NIFTY 50, SENSEX 30 Equities)."""
        instruments = [
            GenericInstrument(
                instrument_key="BSE_INDEX|SENSEX",
                exchange="BSE_INDEX",
                trading_symbol="SENSEX",
                display_name="BSE SENSEX Index",
                instrument_type="INDEX",
                lot_size=10,
            ),
            GenericInstrument(
                instrument_key="NSE_INDEX|Nifty 50",
                exchange="NSE_INDEX",
                trading_symbol="Nifty 50",
                display_name="NIFTY 50 Index",
                instrument_type="INDEX",
                lot_size=25,
            ),
        ]

        # Add SENSEX 30 constituent equities
        for symbol, isin in SENSEX_30_ISINS.items():
            instruments.append(
                GenericInstrument(
                    instrument_key=f"BSE_EQ|{isin}",
                    exchange="BSE_EQ",
                    trading_symbol=symbol,
                    display_name=f"{symbol} Equity (BSE)",
                    instrument_type="EQUITY",
                    isin=isin,
                    lot_size=1,
                )
            )

        self.register_instruments(instruments)

    def register_instruments(self, instruments: List[GenericInstrument]):
        """Registers or updates instruments in SQLite DB."""
        cursor = self.conn.cursor()
        for inst in instruments:
            cursor.execute("""
            INSERT OR REPLACE INTO instruments_master (
                instrument_key, exchange, trading_symbol, display_name,
                instrument_type, isin, tick_size, lot_size, underlying_key, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                inst.instrument_key, inst.exchange, inst.trading_symbol, inst.display_name,
                inst.instrument_type, inst.isin, inst.tick_size, inst.lot_size,
                inst.underlying_key, 1 if inst.is_active else 0
            ))
        self.conn.commit()

    def get_instrument(self, instrument_key: str) -> Optional[GenericInstrument]:
        """Fetch instrument record by key."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT instrument_key, exchange, trading_symbol, display_name, instrument_type, isin, tick_size, lot_size, underlying_key, is_active FROM instruments_master WHERE instrument_key = ?", (instrument_key,))
        row = cursor.fetchone()
        if not row:
            return None
        return GenericInstrument(
            instrument_key=row[0],
            exchange=row[1],
            trading_symbol=row[2],
            display_name=row[3],
            instrument_type=row[4],
            isin=row[5],
            tick_size=row[6],
            lot_size=row[7],
            underlying_key=row[8],
            is_active=bool(row[9]),
        )

    def list_target_instruments(self, exchange_filter: Optional[str] = None) -> List[GenericInstrument]:
        """Lists active target instruments."""
        cursor = self.conn.cursor()
        if exchange_filter:
            cursor.execute("SELECT instrument_key, exchange, trading_symbol, display_name, instrument_type, isin, tick_size, lot_size, underlying_key, is_active FROM instruments_master WHERE exchange = ? AND is_active = 1", (exchange_filter,))
        else:
            cursor.execute("SELECT instrument_key, exchange, trading_symbol, display_name, instrument_type, isin, tick_size, lot_size, underlying_key, is_active FROM instruments_master WHERE is_active = 1")
        
        rows = cursor.fetchall()
        return [
            GenericInstrument(
                instrument_key=r[0], exchange=r[1], trading_symbol=r[2],
                display_name=r[3], instrument_type=r[4], isin=r[5],
                tick_size=r[6], lot_size=r[7], underlying_key=r[8], is_active=bool(r[9])
            )
            for r in rows
        ]

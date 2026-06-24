import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Option Intelligence Platform API"
    DEBUG: bool = True
    
    # Provider Settings
    ACTIVE_PROVIDER: str = "NSE"
    SYMBOLS: List[str] = ["SENSEX", "NIFTY", "BANKNIFTY", "HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "TCS"]
    POLL_INTERVAL_SECONDS: int = 300
    
    # DB settings
    DATABASE_URL: str = "sqlite:///./options_data.db"
    
    # Retention settings (in Days)
    RAW_RESPONSE_RETENTION_DAYS: int = 7
    ONE_MIN_RETENTION_DAYS: int = 7
    FIVE_MIN_RETENTION_DAYS: int = 30
    FIFTEEN_MIN_RETENTION_DAYS: int = 90
    
    # Evidence Engine settings
    # Percentage-based threshold: 0.05% = ~12.5 pts on NIFTY 25000
    OUTCOME_SUCCESS_THRESHOLD_PCT: float = 0.05
    # Points-based threshold: absolute index points (used for cross-symbol comparison in future)
    # NIFTY: 10 pts, BANKNIFTY: 20 pts (adjust per symbol in Sprint 8 when per-symbol config is added)
    OUTCOME_SUCCESS_THRESHOLD_POINTS: float = 10.0
    
    # Sprint 10 Support/Resistance weighting configuration
    OI_WEIGHT: float = 1.0
    CHANGE_OI_WEIGHT: float = 3.0
    
    # Sprint 9 Multi-expiry tracking configuration
    TRACK_EXPIRIES_COUNT: int = 3
    
    # Provider APIs Configuration (Future and Current stubs)
    UPSTOX_API_KEY: str = ""
    UPSTOX_API_SECRET: str = ""
    UPSTOX_ACCESS_TOKEN: str = ""
    ANGEL_CLIENT_ID: str = ""
    ANGEL_PASSWORD: str = ""
    ANGEL_API_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

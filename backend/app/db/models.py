from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.session import Base

class OptionChainSnapshot(Base):
    __tablename__ = "option_chain_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    instrument_type = Column(String(10), default="INDEX")
    expiry_date = Column(String(20), index=True)
    spot_price = Column(Float)
    provider = Column(String(20))
    collection_status = Column(String(20))
    collection_duration_ms = Column(Integer)

    # Relationships
    strikes = relationship("OptionChainStrike", back_populates="snapshot", cascade="all, delete-orphan")


class OptionChainStrike(Base):
    __tablename__ = "option_chain_strikes"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("option_chain_snapshots.id", ondelete="CASCADE"), index=True)
    strike = Column(Float, index=True)
    
    # Call options data
    call_oi = Column(Integer, default=0)
    call_change_oi = Column(Integer, default=0)
    call_volume = Column(Integer, default=0)
    call_iv = Column(Float, default=0.0)
    call_ltp = Column(Float, default=0.0)
    call_bid = Column(Float, default=0.0)
    call_ask = Column(Float, default=0.0)
    call_delta = Column(Float, default=0.0)
    call_gamma = Column(Float, default=0.0)
    call_theta = Column(Float, default=0.0)
    call_vega = Column(Float, default=0.0)
    
    # Put options data
    put_oi = Column(Integer, default=0)
    put_change_oi = Column(Integer, default=0)
    put_volume = Column(Integer, default=0)
    put_iv = Column(Float, default=0.0)
    put_ltp = Column(Float, default=0.0)
    put_bid = Column(Float, default=0.0)
    put_ask = Column(Float, default=0.0)
    put_delta = Column(Float, default=0.0)
    put_gamma = Column(Float, default=0.0)
    put_theta = Column(Float, default=0.0)
    put_vega = Column(Float, default=0.0)

    # Relationship
    snapshot = relationship("OptionChainSnapshot", back_populates="strikes")


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    instrument_type = Column(String(10), default="INDEX")
    expiry_date = Column(String(20), index=True)
    source_snapshot_id = Column(Integer, ForeignKey("option_chain_snapshots.id", ondelete="SET NULL"), nullable=True)
    current_spot = Column(Float)
    pcr = Column(Float)
    market_state = Column(String(30))
    strength = Column(String(10)) # LOW, MEDIUM, HIGH
    iv_change = Column(Float)
    support = Column(Float)
    secondary_support = Column(Float, nullable=True)
    resistance = Column(Float)
    secondary_resistance = Column(Float, nullable=True)
    distance_to_support = Column(Float)
    distance_to_resistance = Column(Float)
    support_strength = Column(String(10)) # LOW, MEDIUM, HIGH
    resistance_strength = Column(String(10)) # LOW, MEDIUM, HIGH


class GeneratedInsight(Base):
    __tablename__ = "generated_insights"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    expiry_date = Column(String(20), index=True, nullable=True)
    category = Column(String(30)) # BUILDUP, VOLATILITY, etc.
    insight_text = Column(String(255))
    confidence_level = Column(String(10)) # LOW, MEDIUM, HIGH
    rule_version = Column(String(10), default="v1.0")


class RawProviderResponse(Base):
    __tablename__ = "raw_provider_responses"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    provider = Column(String(20))
    symbol = Column(String(20), index=True)
    payload_json = Column(Text)


class OptionChainSnapshot5m(Base):
    __tablename__ = "aggregated_5m_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    instrument_type = Column(String(10), default="INDEX")
    expiry_date = Column(String(20), index=True)
    spot_price = Column(Float)
    provider = Column(String(20))
    collection_status = Column(String(20))
    collection_duration_ms = Column(Integer)

    # Relationships
    strikes = relationship("OptionChainStrike5m", back_populates="snapshot", cascade="all, delete-orphan")


class OptionChainStrike5m(Base):
    __tablename__ = "aggregated_5m_strikes"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("aggregated_5m_snapshots.id", ondelete="CASCADE"), index=True)
    strike = Column(Float, index=True)
    
    # Call options data
    call_oi = Column(Integer, default=0)
    call_change_oi = Column(Integer, default=0)
    call_volume = Column(Integer, default=0)
    call_iv = Column(Float, default=0.0)
    call_ltp = Column(Float, default=0.0)
    call_bid = Column(Float, default=0.0)
    call_ask = Column(Float, default=0.0)
    call_delta = Column(Float, default=0.0)
    call_gamma = Column(Float, default=0.0)
    call_theta = Column(Float, default=0.0)
    call_vega = Column(Float, default=0.0)
    
    # Put options data
    put_oi = Column(Integer, default=0)
    put_change_oi = Column(Integer, default=0)
    put_volume = Column(Integer, default=0)
    put_iv = Column(Float, default=0.0)
    put_ltp = Column(Float, default=0.0)
    put_bid = Column(Float, default=0.0)
    put_ask = Column(Float, default=0.0)
    put_delta = Column(Float, default=0.0)
    put_gamma = Column(Float, default=0.0)
    put_theta = Column(Float, default=0.0)
    put_vega = Column(Float, default=0.0)

    # Relationship
    snapshot = relationship("OptionChainSnapshot5m", back_populates="strikes")


class AnalyticsSnapshot5m(Base):
    __tablename__ = "analytics_snapshots_5m"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    instrument_type = Column(String(10), default="INDEX")
    expiry_date = Column(String(20), index=True)
    source_snapshot_id = Column(Integer, ForeignKey("aggregated_5m_snapshots.id", ondelete="SET NULL"), nullable=True)
    current_spot = Column(Float)
    pcr = Column(Float)
    market_state = Column(String(30))
    strength = Column(String(10)) # LOW, MEDIUM, HIGH
    iv_change = Column(Float)
    support = Column(Float)
    secondary_support = Column(Float, nullable=True)
    resistance = Column(Float)
    secondary_resistance = Column(Float, nullable=True)
    distance_to_support = Column(Float)
    distance_to_resistance = Column(Float)
    support_strength = Column(String(10)) # LOW, MEDIUM, HIGH
    resistance_strength = Column(String(10)) # LOW, MEDIUM, HIGH


class OptionChainSnapshot15m(Base):
    __tablename__ = "aggregated_15m_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    instrument_type = Column(String(10), default="INDEX")
    expiry_date = Column(String(20), index=True)
    spot_price = Column(Float)
    provider = Column(String(20))
    collection_status = Column(String(20))
    collection_duration_ms = Column(Integer)

    # Relationships
    strikes = relationship("OptionChainStrike15m", back_populates="snapshot", cascade="all, delete-orphan")


class OptionChainStrike15m(Base):
    __tablename__ = "aggregated_15m_strikes"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("aggregated_15m_snapshots.id", ondelete="CASCADE"), index=True)
    strike = Column(Float, index=True)
    
    # Call options data
    call_oi = Column(Integer, default=0)
    call_change_oi = Column(Integer, default=0)
    call_volume = Column(Integer, default=0)
    call_iv = Column(Float, default=0.0)
    call_ltp = Column(Float, default=0.0)
    call_bid = Column(Float, default=0.0)
    call_ask = Column(Float, default=0.0)
    call_delta = Column(Float, default=0.0)
    call_gamma = Column(Float, default=0.0)
    call_theta = Column(Float, default=0.0)
    call_vega = Column(Float, default=0.0)
    
    # Put options data
    put_oi = Column(Integer, default=0)
    put_change_oi = Column(Integer, default=0)
    put_volume = Column(Integer, default=0)
    put_iv = Column(Float, default=0.0)
    put_ltp = Column(Float, default=0.0)
    put_bid = Column(Float, default=0.0)
    put_ask = Column(Float, default=0.0)
    put_delta = Column(Float, default=0.0)
    put_gamma = Column(Float, default=0.0)
    put_theta = Column(Float, default=0.0)
    put_vega = Column(Float, default=0.0)

    # Relationship
    snapshot = relationship("OptionChainSnapshot15m", back_populates="strikes")


class AnalyticsSnapshot15m(Base):
    __tablename__ = "analytics_snapshots_15m"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    instrument_type = Column(String(10), default="INDEX")
    expiry_date = Column(String(20), index=True)
    source_snapshot_id = Column(Integer, ForeignKey("aggregated_15m_snapshots.id", ondelete="SET NULL"), nullable=True)
    current_spot = Column(Float)
    pcr = Column(Float)
    market_state = Column(String(30))
    strength = Column(String(10)) # LOW, MEDIUM, HIGH
    iv_change = Column(Float)
    support = Column(Float)
    secondary_support = Column(Float, nullable=True)
    resistance = Column(Float)
    secondary_resistance = Column(Float, nullable=True)
    distance_to_support = Column(Float)
    distance_to_resistance = Column(Float)
    support_strength = Column(String(10)) # LOW, MEDIUM, HIGH
    resistance_strength = Column(String(10)) # LOW, MEDIUM, HIGH


class InsightOutcome(Base):
    __tablename__ = "insight_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("option_chain_snapshots.id", ondelete="CASCADE"), index=True)
    generated_at = Column(DateTime, index=True)
    symbol = Column(String(20), index=True)
    market_state = Column(String(30))
    prediction_direction = Column(String(10)) # BULLISH, BEARISH, NEUTRAL
    spot_at_generation = Column(Float)
    spot_after_5m = Column(Float, nullable=True)
    spot_after_15m = Column(Float, nullable=True)
    spot_after_30m = Column(Float, nullable=True)
    spot_after_60m = Column(Float, nullable=True)
    movement_5m_pct = Column(Float, nullable=True)
    movement_15m_pct = Column(Float, nullable=True)
    movement_30m_pct = Column(Float, nullable=True)
    movement_60m_pct = Column(Float, nullable=True)
    movement_5m_points = Column(Float, nullable=True)
    movement_15m_points = Column(Float, nullable=True)
    movement_30m_points = Column(Float, nullable=True)
    movement_60m_points = Column(Float, nullable=True)
    # --- Sprint 7 MFE/MAE Excursion Fields ---
    max_favorable_move_60m = Column(Float, nullable=True)  # Points: max price move in prediction direction within 60m
    max_adverse_move_60m = Column(Float, nullable=True)    # Points: max price move against prediction within 60m
    time_to_mfe_minutes = Column(Integer, nullable=True)   # Minutes to reach MFE
    time_to_mae_minutes = Column(Integer, nullable=True)   # Minutes to reach MAE
    is_mock = Column(Boolean, default=False, index=True)   # Flag to identify seeded developer mock data
    
    status = Column(String(20), default="PENDING", index=True)


class SystemMetadata(Base):
    __tablename__ = "system_metadata"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLFeatureSnapshot(Base):
    __tablename__ = "ml_feature_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    market_date = Column(String(20), index=True)
    timeframe = Column(String(10), index=True) # 1m, 5m, 15m
    symbol = Column(String(20), index=True)
    expiry_date = Column(String(20), index=True)
    expiry_type = Column(String(10)) # WEEKLY, MONTHLY
    source_snapshot_id = Column(Integer, ForeignKey("option_chain_snapshots.id", ondelete="SET NULL"), nullable=True)

    # Temporal & Session Features
    days_to_expiry = Column(Integer)
    minutes_from_open = Column(Integer)
    minutes_to_close = Column(Integer)
    session_phase = Column(String(20)) # OPENING, MIDDAY, CLOSING
    day_type = Column(String(20)) # EXPIRY_DAY, PRE_EXPIRY, NORMAL, MONTHLY_EXPIRY

    # Data Integrity, Flags & Lag Monitoring
    data_quality_score = Column(Integer)
    snapshot_age_seconds = Column(Float)
    feature_flags = Column(Text) # JSON string representation
    feature_schema_version = Column(String(10), default="v1")

    # Options Sentiment Features
    pcr = Column(Float, nullable=True)
    pcr_velocity = Column(Float, nullable=True)
    oi_imbalance = Column(Float, nullable=True)
    average_iv = Column(Float, nullable=True)
    iv_change = Column(Float, nullable=True)
    total_call_oi = Column(Integer, default=0)
    total_put_oi = Column(Integer, default=0)
    call_change_oi = Column(Integer, default=0)
    put_change_oi = Column(Integer, default=0)

    # Levels & Boundary Features (Normalized)
    distance_to_s1 = Column(Float, nullable=True)
    distance_to_s2 = Column(Float, nullable=True)
    distance_to_r1 = Column(Float, nullable=True)
    distance_to_r2 = Column(Float, nullable=True)
    distance_to_s1_pct = Column(Float, nullable=True)
    distance_to_r1_pct = Column(Float, nullable=True)
    sr_compression = Column(Float, nullable=True)
    support_strength = Column(String(10), nullable=True)
    resistance_strength = Column(String(10), nullable=True)

    # Market State & Microstructure Features
    market_state = Column(String(30), nullable=True)
    market_state_id = Column(Integer, nullable=True) # 0=NEUTRAL, 1=LONG_BUILDUP, 2=SHORT_BUILDUP, 3=SHORT_COVERING, 4=LONG_UNWINDING
    strength = Column(String(10), nullable=True)
    strength_score = Column(Integer, nullable=True) # 1=LOW, 2=MEDIUM, 3=HIGH
    ema20 = Column(Float, nullable=True)
    ema50 = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)
    regime_trend = Column(String(20), nullable=True) # UPTREND, DOWNTREND, RANGE
    order_flow = Column(Float, nullable=True)

    # Retrospective Target Labels
    return_15m_pct = Column(Float, nullable=True)
    return_30m_pct = Column(Float, nullable=True)
    return_60m_pct = Column(Float, nullable=True)
    return_15m_points = Column(Float, nullable=True)
    return_30m_points = Column(Float, nullable=True)
    return_60m_points = Column(Float, nullable=True)

    direction_15m = Column(String(10), nullable=True) # UP, DOWN, SIDEWAYS
    direction_30m = Column(String(10), nullable=True)
    direction_60m = Column(String(10), nullable=True)

    label_quality = Column(String(20), nullable=True) # FULL, PARTIAL, INCOMPLETE
    available_horizons = Column(Text, nullable=True) # JSON string representation, e.g. ["15m", "30m"]

    # Leakage Protection Flag
    label_ready_at = Column(DateTime, index=True)
    status = Column(String(20), default="PENDING", index=True)


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("option_chain_snapshots.id", ondelete="CASCADE"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    expiry_date = Column(String(20), index=True)
    spot_price = Column(Float)
    signal_type = Column(String(20))          # BUY_CALL, BUY_PUT, NO_TRADE
    suggested_strike = Column(String(20), nullable=True) # e.g. "24100 CE"
    strike_selection_reason = Column(String(30), nullable=True) # e.g. "ATM", "ATM+1", "Highest OI"
    
    # Confidence raw parameters (allows comparing across versions with different count of rules)
    matched_conditions = Column(Integer, default=0)
    total_conditions = Column(Integer, default=0)
    
    reasons = Column(Text)                    # JSON serialized boolean rule state dictionary: e.g. {"price_up": true, "pcr_up": false, ...}
    signal_inputs = Column(Text, nullable=True) # JSON serialized inputs snapshot: e.g. {"spot": 25230, "pcr": 1.12, ...}
    market_state = Column(String(30))         # Buildup state at signal generation
    signal_version = Column(String(10), default="v1", index=True) # Version tracking for signal engines (v1, v2, etc.)
    was_executed = Column(Boolean, default=False) # User executed this signal manually or not
    
    # Sprint 16 V2 additions
    bullish_score = Column(Float, default=0.0)
    bearish_score = Column(Float, default=0.0)
    decision_margin = Column(Float, default=0.0)
    confidence_ratio = Column(Float, default=0.0)
    dynamic_threshold = Column(Float, default=70.0)
    raw_signal = Column(String(20), default="NO_TRADE")
    volume_z_score = Column(Float, default=0.0)
    feature_version = Column(String(10), default="v2.0")
    data_quality_score = Column(Integer, default=100)
    top_contributors = Column(Text, nullable=True)  # JSON serialized list of top contributors
    lifecycle_state = Column(String(20), default="CREATED")  # CREATED, STRENGTHENED, WEAKENED, CANCELLED, EXECUTED
    
    # Excursion & evaluation parameters
    spot_after_15m = Column(Float, nullable=True)
    spot_after_30m = Column(Float, nullable=True)
    spot_after_60m = Column(Float, nullable=True)
    
    move_15m_points = Column(Float, nullable=True)
    move_30m_points = Column(Float, nullable=True)
    move_60m_points = Column(Float, nullable=True)
    
    move_15m_pct = Column(Float, nullable=True)
    move_30m_pct = Column(Float, nullable=True)
    move_60m_pct = Column(Float, nullable=True)
    
    outcome_15m = Column(String(20), default="PENDING") # WIN, LOSS, FLAT, PENDING
    outcome_30m = Column(String(20), default="PENDING")
    outcome_60m = Column(String(20), default="PENDING")
    
    status = Column(String(20), default="PENDING", index=True) # PENDING, COMPLETED


class ManualTraderDecision(Base):
    __tablename__ = "manual_trader_decisions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    expiry_date = Column(String(20), index=True)
    spot_price = Column(Float)
    decision_type = Column(String(20)) # BUY_CALL, BUY_PUT, STAY_OUT
    suggested_strike = Column(String(20), nullable=True) # e.g. "80500 CE"
    confidence_level = Column(String(10)) # LOW, MEDIUM, HIGH
    notes = Column(Text, nullable=True) # JSON structured notes: e.g. {"price_above_vwap": true, ...}
    matched_system_signal_id = Column(Integer, ForeignKey("trading_signals.id", ondelete="SET NULL"), nullable=True)
    was_executed = Column(Boolean, default=True)
    
    # Excursion & evaluation parameters
    spot_after_15m = Column(Float, nullable=True)
    spot_after_30m = Column(Float, nullable=True)
    spot_after_60m = Column(Float, nullable=True)
    
    move_15m_points = Column(Float, nullable=True)
    move_30m_points = Column(Float, nullable=True)
    move_60m_points = Column(Float, nullable=True)
    
    move_15m_pct = Column(Float, nullable=True)
    move_30m_pct = Column(Float, nullable=True)
    move_60m_pct = Column(Float, nullable=True)
    
    outcome_15m = Column(String(20), default="PENDING") # WIN, LOSS, FLAT, PENDING
    outcome_30m = Column(String(20), default="PENDING")
    outcome_60m = Column(String(20), default="PENDING")
    
    status = Column(String(20), default="PENDING", index=True) # PENDING, COMPLETED


class ObservationLog(Base):
    __tablename__ = "observation_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    spot_price = Column(Float)
    market_state = Column(String(30))
    system_signal = Column(String(20)) # BUY_CALL, BUY_PUT, NO_TRADE
    manual_signal = Column(String(20)) # BUY_CALL, BUY_PUT, STAY_OUT, NO_RECORD
    suggested_strike = Column(String(20), nullable=True)
    result_15m = Column(String(20), default="PENDING")
    result_30m = Column(String(20), default="PENDING")
    result_60m = Column(String(20), default="PENDING")
    notes = Column(Text, nullable=True) # JSON details
    manual_decision_id = Column(Integer, ForeignKey("manual_trader_decisions.id", ondelete="SET NULL"), nullable=True)
    system_signal_id = Column(Integer, ForeignKey("trading_signals.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="PENDING", index=True)


class TradeSession(Base):
    __tablename__ = "trade_sessions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(20), unique=True, index=True)  # YYYY-MM-DD
    capital_allocated = Column(Float, default=0.0)
    pnl = Column(Float, default=0.0)
    emotion_rating = Column(String(20), nullable=True)  # e.g., CALM, GREEDY, ANXIOUS
    stopped_reason = Column(String(50), nullable=True)  # e.g., DAILY_PROFIT_LIMIT, DAILY_LOSS_LIMIT, MANUAL
    daily_limit_hit = Column(Boolean, default=False)
    
    # Advanced risk metrics
    trade_count = Column(Integer, default=0)
    winning_streak = Column(Integer, default=0)
    losing_streak = Column(Integer, default=0)
    max_drawdown_today = Column(Float, default=0.0)
    max_profit_today = Column(Float, default=0.0)
    stopped_automatically = Column(Boolean, default=False)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketRegime(Base):
    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    trend = Column(String(20))           # TRENDING, RANGING
    volatility = Column(String(20))      # HIGH, LOW
    session_phase = Column(String(20))   # OPENING, MIDDAY, CLOSING
    regime_confidence = Column(Float, default=0.0)




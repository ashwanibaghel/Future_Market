"""
REST API ENDPOINTS FOR AI TRADER PAPER TRADING CONTROL ROOM (v3.0)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
from app.engine.paper_trading_engine import global_paper_engine

router = APIRouter()


@router.get("/paper-trading/dashboard", summary="Fetch Complete AI Trader Control Room Dashboard State")
def get_paper_trading_dashboard() -> Dict[str, Any]:
    """
    Returns complete Control Room Payload:
    - Top Section: Market, Current Time, Market Status, Playback/Live Mode, Current Candle Time
    - Current AI Decision Card: Decision (BUY CE / BUY PE / SELL CE / SELL PE / NO TRADE), Confidence, Reason, Sentiment, Risk Level
    - Virtual Account: Starting Capital ₹100,000, Current Capital, Today's PnL, Today's ROI %
    - Statistics: Trades, Wins, Losses, No Trade, Win Rate %, Avg Profit, Avg Loss, Max Drawdown
    - Trade History Table: Time, Decision, Entry, Exit, PnL, Reason, Status
    - Model Status Grid: Individual specialized model opinions exposed
    - Decision Fusion Breakdown: Synthesis summary & consensus
    - MOD_13 Reviewer: Retrospective reviewer feedback (NOT trader)
    """
    return global_paper_engine.get_dashboard_data()


@router.post("/paper-trading/mode", summary="Switch Between Playback Mode and Live Market Mode")
def set_paper_trading_mode(
    mode: str = Query("PLAYBACK", description="Mode: 'PLAYBACK' (Historical June-July Replay) or 'LIVE' (Real-Time Market Open)")
) -> Dict[str, Any]:
    """Switches operational mode between PLAYBACK and LIVE."""
    global_paper_engine.set_mode(mode)
    return global_paper_engine.get_dashboard_data()


@router.post("/paper-trading/playback/step", summary="Step 1 Minute Snapshot Forward in Playback Mode")
def step_paper_trading_playback(
    symbol: str = Query("NIFTY", description="Market Symbol (NIFTY, BANKNIFTY, SENSEX)")
) -> Dict[str, Any]:
    """Steps forward 1 minute snapshot from unseen June/July Parquet Store."""
    return global_paper_engine.step_playback(symbol=symbol)


@router.post("/paper-trading/playback/run", summary="Run Playback Engine for N Steps")
def run_paper_trading_playback(
    steps: int = Query(10, description="Number of minute snapshots to step forward"),
    symbol: str = Query("NIFTY", description="Market Symbol")
) -> Dict[str, Any]:
    """Runs playback engine for N consecutive steps."""
    for _ in range(steps):
        global_paper_engine.step_playback(symbol=symbol)
    return global_paper_engine.get_dashboard_data()


@router.post("/paper-trading/reset", summary="Reset Paper Trading Virtual Capital & State")
def reset_paper_trading_account(
    capital: float = Query(100000.0, description="Virtual Starting Capital")
) -> Dict[str, Any]:
    """Resets virtual capital and trade history."""
    global_paper_engine.reset_account(capital=capital)
    return global_paper_engine.get_dashboard_data()

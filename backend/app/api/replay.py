from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db.session import get_db
from app.engine.replay import replay_historical_snapshots

router = APIRouter()


@router.get("/replay/session")
def get_replay_session(
    symbol: str = Query("NIFTY"),
    market_date: str = Query(..., description="IST market date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Replay one bounded Indian market session using an IST calendar date."""
    try:
        session_date = datetime.strptime(market_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="market_date must use YYYY-MM-DD") from exc

    # Stored timestamps are naive UTC. NSE session 09:15-15:30 IST is 03:45-10:00 UTC.
    start_dt = session_date.replace(hour=3, minute=45)
    end_dt = session_date.replace(hour=10, minute=0)
    records = replay_historical_snapshots(db, symbol, start_dt, end_dt)
    return {
        "symbol": symbol.upper(),
        "market_date": market_date,
        "timezone": "Asia/Kolkata",
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "count": len(records),
        "data": records,
    }

@router.get("/replay")
def get_replay(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    start: str = Query(..., description="Start timestamp in ISO 8601 format (e.g. 2026-06-19T09:15:00)"),
    end: str = Query(..., description="End timestamp in ISO 8601 format (e.g. 2026-06-19T10:00:00)"),
    db: Session = Depends(get_db)
):
    """
    Simulates a step-by-step chronological replay of historical option chain snapshots.
    The window is bounded to one day to protect the operational database.
    """
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid start or end date format. Use ISO 8601 format (e.g., 2026-06-19T09:15:00)."
        )

    if start_dt > end_dt:
        raise HTTPException(
            status_code=400,
            detail="Start time must be before end time."
        )

    if end_dt - start_dt > timedelta(days=1):
        raise HTTPException(status_code=400, detail="Replay window cannot exceed 24 hours.")

    try:
        records = replay_historical_snapshots(db, symbol, start_dt, end_dt)
        return {
            "symbol": symbol.upper(),
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "count": len(records),
            "data": records
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute replay simulation: {str(e)}"
        )

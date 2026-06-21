from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.config import settings
from app.engine.replay import replay_historical_snapshots

router = APIRouter()

@router.get("/replay")
def get_replay(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    start: str = Query(..., description="Start timestamp in ISO 8601 format (e.g. 2026-06-19T09:15:00)"),
    end: str = Query(..., description="End timestamp in ISO 8601 format (e.g. 2026-06-19T10:00:00)"),
    db: Session = Depends(get_db)
):
    """
    Simulates a step-by-step chronological replay of historical option chain snapshots.
    Only accessible in DEV/ADMIN mode (when settings.DEBUG is True).
    """
    # Security constraint: DEV/ADMIN mode check
    if not settings.DEBUG:
        raise HTTPException(
            status_code=403,
            detail="Replay API is restricted to DEV/ADMIN environments (settings.DEBUG=True)."
        )

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

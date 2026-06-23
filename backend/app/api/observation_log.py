import csv
import logging
from io import StringIO
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ObservationLog

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/observation-log")
def get_observation_log(symbol: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Returns the daily observation logs.
    """
    query = db.query(ObservationLog)
    if symbol:
        query = query.filter(ObservationLog.symbol == symbol)
    return query.order_by(ObservationLog.timestamp.desc()).all()

@router.get("/observation-log/export-csv")
def export_observation_log_csv(symbol: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Exports the observation logs as a downloadable CSV spreadsheet.
    """
    query = db.query(ObservationLog)
    if symbol:
        query = query.filter(ObservationLog.symbol == symbol)
    logs = query.order_by(ObservationLog.timestamp.desc()).all()
    
    # Create CSV in memory
    f = StringIO()
    writer = csv.writer(f)
    
    # Write header
    writer.writerow([
        "Date", "Time", "Symbol", "Spot Price", "Market State", 
        "System Signal", "Manual Signal", "Strike", 
        "Result 15m", "Result 30m", "Result 60m", "Notes"
    ])
    
    for log in logs:
        # Format timestamp to Date and Time
        dt = log.timestamp
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M:%S")
        
        writer.writerow([
            date_str,
            time_str,
            log.symbol,
            log.spot_price,
            log.market_state,
            log.system_signal,
            log.manual_signal,
            log.suggested_strike or "",
            log.result_15m,
            log.result_30m,
            log.result_60m,
            log.notes or ""
        ])
        
    f.seek(0)
    
    filename = f"observation_log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Create StreamingResponse from the string buffer
    # Note: StringIO needs to be converted/read or we can just yield the rows
    # A cleaner way in FastAPI is to return response with headers
    response_content = f.getvalue()
    
    # Let's import Response
    from fastapi import Response
    return Response(
        content=response_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.db.models import OptionChainSnapshot, OptionChainStrike
from app.config import settings

router = APIRouter()

@router.get("/health")
def get_system_health(db: Session = Depends(get_db)):
    # Check latest snapshot across all monitored symbols
    latest_snapshot = db.query(OptionChainSnapshot).order_by(
        OptionChainSnapshot.timestamp.desc()
    ).first()
    
    if not latest_snapshot:
        return {
            "status": "INITIALIZING",
            "provider": settings.ACTIVE_PROVIDER,
            "last_fetch": None,
            "last_fetch_age_seconds": None,
            "records_collected": 0,
            "message": "No option chain collections have executed yet."
        }
        
    # Count strikes for the latest snapshot
    strikes_count = db.query(OptionChainStrike).filter(
        OptionChainStrike.snapshot_id == latest_snapshot.id
    ).count()
    
    # Calculate age in seconds
    last_fetch_age_seconds = None
    if latest_snapshot.timestamp:
        last_fetch_age_seconds = int((datetime.utcnow() - latest_snapshot.timestamp).total_seconds())
    
    # Calculate status based on last collection status
    status = "OK" if latest_snapshot.collection_status == "SUCCESS" else "ERROR"
    
    return {
        "status": status,
        "provider": latest_snapshot.provider or settings.ACTIVE_PROVIDER,
        "last_fetch": latest_snapshot.timestamp.isoformat() if latest_snapshot.timestamp else None,
        "last_fetch_age_seconds": last_fetch_age_seconds,
        "records_collected": strikes_count,
        "collection_status": latest_snapshot.collection_status,
        "collection_duration_ms": latest_snapshot.collection_duration_ms
    }

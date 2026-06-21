from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from app.db.session import get_db
from app.db.models import OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot

router = APIRouter()

def apply_market_hours_filter(query, date_str: Optional[str] = None):
    """
    Filters snapshots to only include market hours: 09:15 AM to 03:30 PM IST.
    In UTC, this corresponds to 03:45:00 AM to 10:00:00 AM.
    Only allows weekdays (Monday to Friday).
    """
    query = query.filter(
        func.strftime('%H:%M:%S', OptionChainSnapshot.timestamp) >= '03:45:00',
        func.strftime('%H:%M:%S', OptionChainSnapshot.timestamp) <= '10:00:00',
        func.strftime('%w', OptionChainSnapshot.timestamp).in_(['1', '2', '3', '4', '5'])
    )
    if date_str:
        query = query.filter(func.date(OptionChainSnapshot.timestamp) == date_str)
    return query

def get_default_market_date(db: Session, symbol: str) -> Optional[str]:
    """
    Returns the latest date (YYYY-MM-DD) that contains successful snapshots during market hours.
    """
    query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    query = apply_market_hours_filter(query)
    latest = query.order_by(OptionChainSnapshot.timestamp.desc()).first()
    if latest:
        return latest.timestamp.strftime('%Y-%m-%d')
    return None

@router.get("/market-dates")
def get_market_dates(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    db: Session = Depends(get_db)
):
    """
    Returns a distinct list of dates (YYYY-MM-DD) having successful snapshots during market hours.
    """
    query = db.query(func.date(OptionChainSnapshot.timestamp)).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    query = apply_market_hours_filter(query)
    results = query.distinct().all()
    
    dates = [r[0] for r in results if r[0]]
    dates.sort(reverse=True)
    return dates

@router.get("/option-chain")
def get_option_chain(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    expiry: Optional[str] = Query(None, description="Specific expiry date string"),
    date: Optional[str] = Query(None, description="Selected date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    if not date:
        date = get_default_market_date(db, symbol)
        
    if not date:
        raise HTTPException(
            status_code=404,
            detail=f"No successful market hours snapshots found for symbol {symbol}"
        )

    # Query snapshots for the given symbol, date, and successful status
    query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    query = apply_market_hours_filter(query, date)
    
    if not expiry:
        # Default to the nearest active expiry date at the latest crawled timestamp on that date
        latest_snap_any = db.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == symbol.upper(),
            OptionChainSnapshot.collection_status == "SUCCESS"
        )
        latest_snap_any = apply_market_hours_filter(latest_snap_any, date)
        latest_snap_any = latest_snap_any.order_by(OptionChainSnapshot.timestamp.desc()).first()
        
        if latest_snap_any:
            # Query all successful expiries at this latest snapshot timestamp
            expiries_at_ts = db.query(OptionChainSnapshot.expiry_date).filter(
                OptionChainSnapshot.symbol == symbol.upper(),
                OptionChainSnapshot.collection_status == "SUCCESS",
                func.datetime(OptionChainSnapshot.timestamp) == func.datetime(latest_snap_any.timestamp)
            ).all()
            
            # Extract and sort expiries
            expiries = [e[0] for e in expiries_at_ts if e[0]]
            
            def parse_date(date_str):
                from datetime import datetime
                try:
                    return datetime.strptime(date_str, "%d-%b-%Y")
                except Exception:
                    return datetime.max
            
            expiries.sort(key=parse_date)
            if expiries:
                expiry = expiries[0]
                
    if expiry:
        query = query.filter(OptionChainSnapshot.expiry_date == expiry)
        
    latest_snapshot = query.order_by(OptionChainSnapshot.timestamp.desc()).first()
    
    if not latest_snapshot:
        raise HTTPException(
            status_code=404, 
            detail=f"No successful option chain snapshots found for symbol {symbol}" + 
                   (f" with expiry {expiry}" if expiry else "") +
                   (f" on date {date}" if date else "")
        )
        
    # Fetch strikes for this snapshot
    strikes = db.query(OptionChainStrike).filter(
        OptionChainStrike.snapshot_id == latest_snapshot.id
    ).order_by(OptionChainStrike.strike.asc()).all()
    
    # Query matching analytics snapshot
    analytics = db.query(AnalyticsSnapshot).filter(
        AnalyticsSnapshot.source_snapshot_id == latest_snapshot.id
    ).first()
    
    analytics_data = None
    if analytics:
        analytics_data = {
            "pcr": analytics.pcr,
            "support": analytics.support,
            "secondary_support": analytics.secondary_support,
            "resistance": analytics.resistance,
            "secondary_resistance": analytics.secondary_resistance,
            "distance_to_support": analytics.distance_to_support,
            "distance_to_resistance": analytics.distance_to_resistance,
            "support_strength": analytics.support_strength,
            "resistance_strength": analytics.resistance_strength,
            "market_state": analytics.market_state,
            "strength": analytics.strength,
            "iv_change": analytics.iv_change
        }
    
    return {
        "symbol": latest_snapshot.symbol,
        "timestamp": latest_snapshot.timestamp,
        "expiry_date": latest_snapshot.expiry_date,
        "spot_price": latest_snapshot.spot_price,
        "provider": latest_snapshot.provider,
        "collection_duration_ms": latest_snapshot.collection_duration_ms,
        "analytics": analytics_data,
        "strikes": [
            {
                "strike": s.strike,
                "call_oi": s.call_oi,
                "call_change_oi": s.call_change_oi,
                "call_volume": s.call_volume,
                "call_iv": s.call_iv,
                "call_ltp": s.call_ltp,
                "call_bid": s.call_bid,
                "call_ask": s.call_ask,
                "put_oi": s.put_oi,
                "put_change_oi": s.put_change_oi,
                "put_volume": s.put_volume,
                "put_iv": s.put_iv,
                "put_ltp": s.put_ltp,
                "put_bid": s.put_bid,
                "put_ask": s.put_ask
            }
            for s in strikes
        ]
    }

@router.get("/latest-snapshot")
def get_latest_snapshot(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    expiry: Optional[str] = Query(None, description="Optional expiry date string"),
    date: Optional[str] = Query(None, description="Selected date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    if not date:
        date = get_default_market_date(db, symbol)
        
    query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    query = apply_market_hours_filter(query, date)
    
    if expiry:
        query = query.filter(OptionChainSnapshot.expiry_date == expiry)
        
    latest_snapshot = query.order_by(OptionChainSnapshot.timestamp.desc()).first()
    
    if not latest_snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No successful snapshots found for symbol {symbol}" +
                   (f" with expiry {expiry}" if expiry else "") +
                   (f" on date {date}" if date else "")
        )
        
    return {
        "symbol": latest_snapshot.symbol,
        "timestamp": latest_snapshot.timestamp.isoformat() if latest_snapshot.timestamp else None,
        "spot_price": latest_snapshot.spot_price,
        "expiry": latest_snapshot.expiry_date
    }

@router.get("/expiries")
def get_active_expiries(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    date: Optional[str] = Query(None, description="Selected date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    if not date:
        date = get_default_market_date(db, symbol)
        
    if not date:
        return []
        
    # Query unique expiries at the latest successful snapshot timestamp
    query = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS"
    )
    query = apply_market_hours_filter(query, date)
    latest_snap = query.order_by(OptionChainSnapshot.timestamp.desc()).first()
    
    if not latest_snap:
        return []
        
    expiries_at_ts = db.query(OptionChainSnapshot.expiry_date).filter(
        OptionChainSnapshot.symbol == symbol.upper(),
        OptionChainSnapshot.collection_status == "SUCCESS",
        func.datetime(OptionChainSnapshot.timestamp) == func.datetime(latest_snap.timestamp)
    ).distinct().all()
    
    expiries = [e[0] for e in expiries_at_ts if e[0]]
    
    def parse_date(date_str):
        from datetime import datetime
        try:
            return datetime.strptime(date_str, "%d-%b-%Y")
        except Exception:
            return datetime.max
            
    expiries.sort(key=parse_date)
    return expiries

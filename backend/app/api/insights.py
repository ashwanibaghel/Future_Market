from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.db.session import get_db
from app.db.models import GeneratedInsight

router = APIRouter()

@router.get("/insights")
def get_insights(
    symbol: str = Query("NIFTY", description="Symbol name (e.g. NIFTY, BANKNIFTY)"),
    expiry: Optional[str] = Query(None, description="Optional expiry date string"),
    date: Optional[str] = Query(None, description="Selected date (YYYY-MM-DD)"),
    limit: int = Query(5, description="Maximum number of insights to return"),
    db: Session = Depends(get_db)
):
    query = db.query(GeneratedInsight).filter(
        GeneratedInsight.symbol == symbol.upper()
    )
    if expiry:
        query = query.filter(GeneratedInsight.expiry_date == expiry)
        
    if date:
        query = query.filter(func.date(GeneratedInsight.timestamp) == date)
        
    insights = query.order_by(GeneratedInsight.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": insight.id,
            "timestamp": insight.timestamp,
            "symbol": insight.symbol,
            "category": insight.category,
            "insight_text": insight.insight_text,
            "confidence_level": insight.confidence_level,
            "rule_version": insight.rule_version
        }
        for insight in insights
    ]

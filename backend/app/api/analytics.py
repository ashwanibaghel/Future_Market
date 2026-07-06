import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import DailyReport
from app.engine.validation import generate_daily_validation_report

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/analytics/reports")
def list_reports(
    db: Session = Depends(get_db)
):
    """
    Returns a list of all compiled daily validation reports.
    """
    reports = db.query(DailyReport).order_by(DailyReport.date.desc()).all()
    result = []
    for r in reports:
        import json
        summary = {}
        try:
            summary = json.loads(r.summary_json) if r.summary_json else {}
        except Exception:
            pass
            
        result.append({
            "id": r.id,
            "date": r.date,
            "summary": summary.get("summary", {})
        })
    return result

@router.get("/analytics/reports/{date}")
def get_report_detail(
    date: str,
    db: Session = Depends(get_db)
):
    """
    Returns detailed JSON statistics and pre-rendered Markdown for a specific date.
    """
    report = db.query(DailyReport).filter(DailyReport.date == date).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for date: {date}")
        
    import json
    summary = {}
    try:
        summary = json.loads(report.summary_json) if report.summary_json else {}
    except Exception:
        pass
        
    return {
        "id": report.id,
        "date": report.date,
        "summary": summary,
        "markdown": report.markdown_content
    }

@router.post("/analytics/reports/trigger")
def trigger_report_generation(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    version: str = Query("v2.5", description="Signal engine version (v2, v2.5)"),
    db: Session = Depends(get_db)
):
    """
    Manually triggers generation or regeneration of a daily validation report.
    """
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    try:
        report = generate_daily_validation_report(db, date, version)
        import json
        summary = {}
        try:
            summary = json.loads(report.summary_json) if report.summary_json else {}
        except Exception:
            pass
            
        return {
            "success": True,
            "message": f"Report compiled successfully for {date}",
            "report": {
                "id": report.id,
                "date": report.date,
                "summary": summary
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate report for {date}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

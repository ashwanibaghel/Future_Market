from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.mission_control.auto_repair_engine import run_auto_repair_dry_run
from app.mission_control.constitution_engine import run_constitution_checks
from app.mission_control.dataset_inspector import build_dataset_health, inspect_dataset
from app.mission_control.execution_intelligence import get_execution_intelligence
from app.mission_control.lineage_engine import get_lineage_summary
from app.mission_control.pattern_intelligence import get_pattern_intelligence
from app.mission_control.replay_intelligence import get_replay_intelligence, get_replay_session_contract
from app.mission_control.roadmap_engine import get_project_tracker
from app.mission_control.rule_audit_engine import get_rule_audit
from app.mission_control.service import build_overview
from app.mission_control.training_forecast import get_training_forecast

router = APIRouter()


@router.get("/mission-control/overview")
def mission_control_overview(
    symbol: str | None = Query(None),
    market_date: str | None = Query(None, description="Market date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    return build_overview(db, symbol=symbol, market_date=market_date)


@router.get("/mission-control/roadmap")
def mission_control_roadmap():
    return get_project_tracker()


@router.get("/mission-control/constitution")
def mission_control_constitution(db: Session = Depends(get_db)):
    return run_constitution_checks(db)


@router.get("/mission-control/dataset-health")
def mission_control_dataset_health(
    symbol: str | None = Query(None),
    market_date: str | None = Query(None, description="Market date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    return build_dataset_health(db, symbol=symbol, market_date=market_date)


@router.get("/mission-control/inspector")
def mission_control_inspector(
    symbol: str | None = Query(None),
    market_date: str | None = Query(None, description="Market date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    return {"evidence": [item.model_dump() for item in inspect_dataset(db, symbol=symbol, market_date=market_date)]}


@router.get("/mission-control/lineage")
def mission_control_lineage(
    symbol: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_lineage_summary(db, symbol=symbol)


@router.get("/mission-control/replay-intelligence")
def mission_control_replay_intelligence(
    symbol: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_replay_intelligence(db, symbol=symbol)


@router.get("/mission-control/replay-contract")
def mission_control_replay_contract(market_date: str = Query(..., description="Market date YYYY-MM-DD")):
    return get_replay_session_contract(market_date)


@router.get("/mission-control/pattern-intelligence")
def mission_control_pattern_intelligence(
    symbol: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_pattern_intelligence(db, symbol=symbol)


@router.get("/mission-control/rule-audit")
def mission_control_rule_audit(
    symbol: str | None = Query(None),
    version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_rule_audit(db, symbol=symbol, version=version)


@router.get("/mission-control/execution-intelligence")
def mission_control_execution_intelligence(
    symbol: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_execution_intelligence(db, symbol=symbol)


@router.get("/mission-control/training-forecast")
def mission_control_training_forecast(
    symbol: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_training_forecast(db, symbol=symbol)


@router.get("/mission-control/auto-repair")
def mission_control_auto_repair(
    symbol: str | None = Query(None),
    market_date: str | None = Query(None, description="Market date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    overview = build_overview(db, symbol=symbol, market_date=market_date)
    return overview["auto_repair"]


@router.post("/mission-control/auto-repair/dry-run")
def mission_control_auto_repair_dry_run(
    symbol: str | None = Query(None),
    market_date: str | None = Query(None, description="Market date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    overview = build_overview(db, symbol=symbol, market_date=market_date)
    return run_auto_repair_dry_run(overview["auto_repair"])

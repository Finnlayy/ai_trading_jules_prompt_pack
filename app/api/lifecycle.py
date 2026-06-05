"""API endpoints for paper-training lifecycle visibility."""

from __future__ import annotations

from typing import Any
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import AgentLearningEvent, AgentReviewEvent, PaperOutcome, SignalCandidate
from app.services.paper_training_engine import EngineAction, paper_training_engine

router = APIRouter()


class EngineControlRequest(BaseModel):
    action: EngineAction


def _dt(value) -> str | None:
    return value.isoformat() if value else None


@router.get("/summary")
def lifecycle_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return aggregate state for the paper-training lifecycle."""
    total_candidates = db.query(SignalCandidate).count()
    open_candidates = (
        db.query(SignalCandidate)
        .filter(SignalCandidate.status.in_(["created", "ai_reviewed", "paper_opened"]))
        .count()
    )
    outcomes = db.query(PaperOutcome).all()
    wins = sum(1 for outcome in outcomes if outcome.win)
    losses = len(outcomes) - wins
    total_pnl = sum(float(outcome.pnl or 0.0) for outcome in outcomes)
    avg_r = (
        sum(float(outcome.r_multiple or 0.0) for outcome in outcomes) / len(outcomes)
        if outcomes else 0.0
    )
    learning_events = db.query(AgentLearningEvent).count()
    scout_accuracy: dict[str, dict[str, Any]] = {}
    for event in db.query(AgentLearningEvent).all():
        row = scout_accuracy.setdefault(event.scout_name, {"total": 0, "correct": 0, "accuracy": 0.0})
        row["total"] += 1
        if event.was_correct:
            row["correct"] += 1
    for row in scout_accuracy.values():
        row["accuracy"] = row["correct"] / row["total"] if row["total"] else 0.0

    return {
        "status": "ok",
        "candidates": {
            "total": total_candidates,
            "open": open_candidates,
            "closed": db.query(SignalCandidate).filter(SignalCandidate.status == "paper_closed").count(),
        },
        "outcomes": {
            "total": len(outcomes),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(outcomes) if outcomes else 0.0,
            "total_pnl": round(total_pnl, 8),
            "avg_r_multiple": round(avg_r, 4),
        },
        "learning": {
            "events": learning_events,
            "scout_accuracy": scout_accuracy,
        },
    }


@router.get("/engine/status")
def paper_training_engine_status() -> dict[str, Any]:
    """Return the combined paper-training engine runtime status."""
    return paper_training_engine.status()


@router.post("/engine/control")
def control_paper_training_engine(req: EngineControlRequest) -> dict[str, Any]:
    """Control the live-paper training engine as one coordinated runtime."""
    try:
        return paper_training_engine.control(req.action)
    except RuntimeError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/candidates")
def list_candidates(
    limit: int = Query(default=50, ge=1, le=500),
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_\-\.]+$"),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent signal candidates."""
    query = db.query(SignalCandidate)
    if symbol:
        query = query.filter(SignalCandidate.symbol == symbol.upper())
    if status:
        query = query.filter(SignalCandidate.status == status)
    rows = query.order_by(SignalCandidate.created_at.desc()).limit(limit).all()
    return {
        "status": "ok",
        "count": len(rows),
        "items": [
            {
                "candidate_id": row.candidate_id,
                "signal_id": row.signal_id,
                "symbol": row.symbol,
                "timeframe": row.timeframe,
                "strategy_id": row.strategy_id,
                "direction": row.direction,
                "entry_price": row.entry_price,
                "stop_price": row.stop_price,
                "target_price": row.target_price,
                "confluence_score": row.confluence_score,
                "status": row.status,
                "source": row.source,
                "bar_timestamp": _dt(row.bar_timestamp),
                "created_at": _dt(row.created_at),
                "processed_at": _dt(row.processed_at),
            }
            for row in rows
        ],
    }


@router.get("/outcomes")
def list_outcomes(
    limit: int = Query(default=50, ge=1, le=500),
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_\-\.]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent closed paper outcomes."""
    query = db.query(PaperOutcome)
    if symbol:
        query = query.filter(PaperOutcome.symbol == symbol.upper())
    rows = query.order_by(PaperOutcome.created_at.desc()).limit(limit).all()
    return {
        "status": "ok",
        "count": len(rows),
        "items": [
            {
                "candidate_id": row.candidate_id,
                "trade_id": row.trade_id,
                "signal_id": row.signal_id,
                "symbol": row.symbol,
                "direction": row.direction,
                "strategy_id": row.strategy_id,
                "timeframe": row.timeframe,
                "close_reason": row.close_reason,
                "exit_price": row.exit_price,
                "pnl": row.pnl,
                "pnl_pct": row.pnl_pct,
                "r_multiple": row.r_multiple,
                "win": row.win,
                "duration_seconds": row.duration_seconds,
                "outcome_source": row.outcome_source,
                "created_at": _dt(row.created_at),
            }
            for row in rows
        ],
    }


@router.get("/learning")
def list_learning_events(
    limit: int = Query(default=100, ge=1, le=1000),
    scout_name: str | None = Query(default=None),
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_\-\.]+$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent scout learning attribution events."""
    query = db.query(AgentLearningEvent)
    if scout_name:
        query = query.filter(AgentLearningEvent.scout_name == scout_name)
    if symbol:
        query = query.filter(AgentLearningEvent.symbol == symbol.upper())
    rows = query.order_by(AgentLearningEvent.created_at.desc()).limit(limit).all()
    return {
        "status": "ok",
        "count": len(rows),
        "items": [
            {
                "candidate_id": row.candidate_id,
                "trade_id": row.trade_id,
                "signal_id": row.signal_id,
                "scout_name": row.scout_name,
                "symbol": row.symbol,
                "direction": row.direction,
                "strategy_id": row.strategy_id,
                "timeframe": row.timeframe,
                "was_correct": row.was_correct,
                "outcome_source": row.outcome_source,
                "created_at": _dt(row.created_at),
            }
            for row in rows
        ],
    }


@router.get("/reviews/{candidate_id}")
def list_candidate_reviews(candidate_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return stored scout reviews for a candidate."""
    rows = (
        db.query(AgentReviewEvent)
        .filter(AgentReviewEvent.candidate_id == candidate_id)
        .order_by(AgentReviewEvent.created_at.desc())
        .all()
    )
    return {
        "status": "ok",
        "candidate_id": candidate_id,
        "count": len(rows),
        "items": [
            {
                "scout_name": row.scout_name,
                "decision": row.decision,
                "confidence": row.confidence,
                "provider": row.provider,
                "model": row.model,
                "created_at": _dt(row.created_at),
            }
            for row in rows
        ],
    }

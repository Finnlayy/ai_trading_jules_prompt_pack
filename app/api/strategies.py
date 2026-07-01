"""API endpoints for strategy management and switching."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from datetime import datetime, timezone, timedelta

from app.schemas.strategy import (
    StrategyConfig,
    StrategyHealthItem,
    StrategyHealthResponse,
    StrategySmokeRequest,
    StrategySmokeResponse,
    StrategyStatusResponse,
    StrategySwitchRequest,
)
from app.services.strategy_engine import strategy_registry
from app.services.confidence_registry import confidence_registry
from app.services.journal_logger import journal_logger_instance
from app.services.signal_generator import BybitDataFeed

router = APIRouter()


def _metadata_to_config(meta) -> StrategyConfig:
    return StrategyConfig(
        strategy_id=meta.strategy_id,
        name=meta.name,
        description=meta.description,
        strategy_type=meta.strategy_type,  # type: ignore[arg-type]
        timeframes=meta.timeframes,
        created_at=meta.created_at,
        updated_at=meta.updated_at,
    )


@router.get("", response_model=StrategyStatusResponse)
async def list_strategies():
    """List all registered strategies and active configuration."""
    configs = [_metadata_to_config(m) for m in strategy_registry.list_metadata()]
    return StrategyStatusResponse(
        active_strategy_id=strategy_registry.active_strategy_id,
        available_strategies=configs,
        last_switch=strategy_registry.last_switch,
        pattern_stats={},
    )


@router.get("/library")
def get_strategy_library():
    """Return all strategies along with their code, file links, and tags."""
    from pathlib import Path
    from app.services.strategy_engine import strategy_registry
    
    library = []
    metadata_list = strategy_registry.list_metadata()
    for meta in metadata_list:
        strat_id = meta.strategy_id
        name = meta.name
        desc = meta.description
        stype = meta.strategy_type
        timeframes = meta.timeframes
        
        filepath = None
        tags = ["Core"]
        if stype == "pine_placeholder":
            tags.append("Pine Script v6")
            base_dir = Path("app/scripts/generated_pines")
            fpath = base_dir / f"{strat_id}.pine"
            if fpath.exists():
                filepath = str(fpath)
            else:
                for f in base_dir.glob("*.pine"):
                    if f.stem == strat_id or f.stem.lower() == strat_id.lower():
                        filepath = str(f)
                        break
        else:
            tags.append("Python")
            filepath = "app/services/strategy_engine.py"
            
        code = None
        if filepath and filepath.endswith(".pine"):
            try:
                code = Path(filepath).read_text(encoding="utf-8")
            except Exception:
                pass
                
        library.append({
            "strategy_id": strat_id,
            "name": name,
            "description": desc,
            "strategy_type": stype,
            "timeframes": timeframes,
            "filepath": filepath,
            "tags": tags,
            "code": code,
        })
        
    return {
        "status": "ok",
        "strategies": library,
    }



@router.get("/active", response_model=StrategyConfig)
async def get_active_strategy():
    """Return metadata for the currently active strategy."""
    strategy = strategy_registry.get_active_strategy()
    return _metadata_to_config(strategy.get_metadata())


@router.post("/switch")
async def switch_strategy(req: StrategySwitchRequest):
    """Switch the active strategy at runtime."""
    try:
        strategy_registry.set_active_strategy(req.strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "success": True,
        "active_strategy_id": strategy_registry.active_strategy_id,
        "last_switch": strategy_registry.last_switch,
    }


@router.post("/{strategy_id}/backtest-smoke", response_model=StrategySmokeResponse)
async def backtest_smoke(strategy_id: str, req: StrategySmokeRequest | None = None):
    """
    Run a quick smoke-test of a strategy on the most recent bars.
    Does NOT persist anything — purely diagnostic.
    """
    if req is None:
        req = StrategySmokeRequest()

    try:
        strategy = strategy_registry.get(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        bars = BybitDataFeed.fetch(req.symbol, bars=req.bars, timeframe=req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if len(bars) < 20:
        raise HTTPException(status_code=422, detail="Insufficient bars for scoring")

    scores = strategy.score_bars(bars)
    signals = [s for s in scores if s.direction != "NEUTRAL" and s.confluence_score >= req.min_confluence]
    max_conf = max((s.confluence_score for s in scores), default=0.0)

    sample = [
        {
            "direction": s.direction,
            "confluence_score": s.confluence_score,
            "confidence": s.confidence,
            "metadata": s.metadata,
        }
        for s in scores[:5]
    ]

    return StrategySmokeResponse(
        strategy_id=strategy_id,
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars_scored=len(scores),
        signals_generated=len(signals),
        max_confluence=round(max_conf, 2),
        sample_scores=sample,
    )


@router.get("/health", response_model=StrategyHealthResponse)
async def get_strategies_health():
    """
    Return a health dashboard for every registered strategy.
    Aggregates per-strategy metrics from the SQL database (outcomes and candidates).
    """
    from sqlalchemy import func
    from app.db import SessionLocal
    from app.db.models import PaperOutcome, SignalCandidate
    
    all_strategies = strategy_registry.list_metadata()
    active_id = strategy_registry.active_strategy_id
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    items: list[StrategyHealthItem] = []
    
    with SessionLocal() as db:
        # 1. Fetch all outcomes grouped by strategy_id
        all_outcomes = db.query(PaperOutcome).all()
        outcomes_by_strat = {}
        for o in all_outcomes:
            outcomes_by_strat.setdefault(o.strategy_id, []).append(o)

        # 2. Bulk fetch signal counts
        signal_counts = db.query(
            SignalCandidate.strategy_id,
            func.count(SignalCandidate.id).label('total')
        ).group_by(SignalCandidate.strategy_id).all()
        total_signals_map = {row.strategy_id: row.total for row in signal_counts}

        # 3. Bulk fetch 24h signal counts
        signal_counts_24h = db.query(
            SignalCandidate.strategy_id,
            func.count(SignalCandidate.id).label('total')
        ).filter(SignalCandidate.created_at >= cutoff).group_by(SignalCandidate.strategy_id).all()
        signals_24h_map = {row.strategy_id: row.total for row in signal_counts_24h}

        # 4. Bulk fetch last signal timestamps
        last_candidates = db.query(
            SignalCandidate.strategy_id,
            func.max(SignalCandidate.created_at).label('last_time')
        ).group_by(SignalCandidate.strategy_id).all()
        last_candidate_map = {row.strategy_id: row.last_time for row in last_candidates}

        # 5. Bulk fetch last outcome timestamps
        last_outcomes = db.query(
            PaperOutcome.strategy_id,
            func.max(PaperOutcome.created_at).label('last_time')
        ).group_by(PaperOutcome.strategy_id).all()
        last_outcome_map = {row.strategy_id: row.last_time for row in last_outcomes}

        for meta in all_strategies:
            last_switch = strategy_registry.last_switch if meta.strategy_id == active_id else None
            
            outcomes = outcomes_by_strat.get(meta.strategy_id, [])
            total_signals = total_signals_map.get(meta.strategy_id, 0)
            signal_count_24h = signals_24h_map.get(meta.strategy_id, 0)
            
            # Calculate win rate, profit factor, avg pnl pct
            total_trades = len(outcomes)
            total_wins = sum(1 for o in outcomes if o.win)
            win_rate = total_wins / total_trades if total_trades > 0 else 0.0
            
            gross_profit = sum(o.pnl for o in outcomes if o.win and o.pnl is not None)
            gross_loss = sum(abs(o.pnl) for o in outcomes if not o.win and o.pnl is not None)
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
            
            avg_pnl_pct = sum(o.pnl_pct for o in outcomes if o.pnl_pct is not None) / total_trades if total_trades > 0 else 0.0
            
            # Max drawdown calculation
            sorted_outcomes = sorted(outcomes, key=lambda x: x.created_at or datetime.min)
            cum_pnl = 0.0
            peak = 0.0
            max_dd = 0.0
            for o in sorted_outcomes:
                cum_pnl += o.pnl_pct or 0.0
                if cum_pnl > peak:
                    peak = cum_pnl
                dd = peak - cum_pnl
                if dd > max_dd:
                    max_dd = dd
            max_drawdown_pct = max_dd
            
            # Last signal/trade age
            c_ts = last_candidate_map.get(meta.strategy_id)
            o_ts = last_outcome_map.get(meta.strategy_id)
            
            last_ts = None
            if c_ts:
                if c_ts.tzinfo is None:
                    c_ts = c_ts.replace(tzinfo=timezone.utc)
                last_ts = c_ts
            if o_ts:
                if o_ts.tzinfo is None:
                    o_ts = o_ts.replace(tzinfo=timezone.utc)
                if last_ts is None or o_ts > last_ts:
                    last_ts = o_ts
                    
            best_age = (now - last_ts).total_seconds() if last_ts else None
            
            # Health Score
            score = 0.0
            if total_trades > 0:
                score += min(win_rate * 100, 40)
                score += min(profit_factor * 20, 20)
                if best_age is not None:
                    recency_score = max(0, 20 - (best_age / 3600))  # decays over 20h
                    score += recency_score
                volume_score = min(total_trades / 10, 20)  # 20 trades = full score
                score += volume_score
            if meta.strategy_id == active_id:
                score += 5.0
            score = round(max(0.0, min(100.0, score)), 1)
            
            items.append(
                StrategyHealthItem(
                    strategy_id=meta.strategy_id,
                    name=meta.name,
                    description=meta.description,
                    is_active=meta.strategy_id == active_id,
                    last_switch=last_switch,
                    total_signals=total_signals,
                    win_rate=round(win_rate, 4),
                    profit_factor=round(profit_factor, 2),
                    avg_pnl_pct=round(avg_pnl_pct, 4),
                    max_drawdown_pct=round(max_drawdown_pct, 4),
                    last_signal_age_seconds=best_age,
                    health_score=score,
                    signal_count_24h=signal_count_24h,
                )
            )

    return StrategyHealthResponse(strategies=items)

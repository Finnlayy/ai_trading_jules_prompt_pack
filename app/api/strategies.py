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
    Aggregates system-wide metrics from ConfidenceRegistry and JournalLogger.
    """
    aggregate = confidence_registry.get_aggregate_stats()
    all_strategies = strategy_registry.list_metadata()
    active_id = strategy_registry.active_strategy_id
    now = datetime.now(timezone.utc)

    # Count journal entries in last 24h (system-wide proxy since journal lacks strategy_id)
    try:
        entries = journal_logger_instance.get_entries(limit=5000)
        cutoff = now - timedelta(hours=24)
        signal_count_24h = 0
        last_journal_ts = None
        for entry in entries:
            ts_str = entry.get("timestamp") or entry.get("created_at")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if last_journal_ts is None or ts > last_journal_ts:
                    last_journal_ts = ts
                if ts >= cutoff:
                    signal_count_24h += 1
            except (ValueError, TypeError):
                continue
    except Exception:
        entries = []
        signal_count_24h = 0
        last_journal_ts = None

    # Use the most recent timestamp we have (journal or registry)
    registry_age = aggregate.get("last_signal_age_seconds")
    journal_age = (now - last_journal_ts).total_seconds() if last_journal_ts else None
    if registry_age is not None and journal_age is not None:
        best_age = min(registry_age, journal_age)
    elif registry_age is not None:
        best_age = registry_age
    else:
        best_age = journal_age

    items: list[StrategyHealthItem] = []
    for meta in all_strategies:
        last_switch = strategy_registry.last_switch if meta.strategy_id == active_id else None
        # Derive a per-strategy health score that nudges active strategy up slightly
        base_score = aggregate.get("health_score", 0.0)
        score = base_score + (5.0 if meta.strategy_id == active_id else 0.0)
        score = round(min(100.0, score), 1)

        items.append(
            StrategyHealthItem(
                strategy_id=meta.strategy_id,
                name=meta.name,
                description=meta.description,
                is_active=meta.strategy_id == active_id,
                last_switch=last_switch,
                total_signals=aggregate.get("total_signals", 0),
                win_rate=aggregate.get("win_rate", 0.0),
                profit_factor=aggregate.get("profit_factor", 0.0),
                avg_pnl_pct=aggregate.get("avg_pnl_pct", 0.0),
                max_drawdown_pct=aggregate.get("max_drawdown_pct", 0.0),
                last_signal_age_seconds=best_age,
                health_score=score,
                signal_count_24h=signal_count_24h,
            )
        )

    return StrategyHealthResponse(strategies=items)

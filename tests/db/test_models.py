"""Tests for SQLAlchemy DB models and repositories."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.db.models import Trade, Position, PerformanceSnapshot, StrategyRotation, NewsImpact
from app.db.repository import (
    TradeRepository,
    PositionRepository,
    PerformanceRepository,
    StrategyRotationRepository,
    NewsImpactRepository,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite DB for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Trade tests
# ---------------------------------------------------------------------------

def test_trade_create(db_session):
    repo = TradeRepository(db_session)
    trade = repo.create(
        trade_id="t-001",
        signal_id="s-001",
        symbol="BTCUSDT",
        direction="LONG",
        strategy_id="default",
        entry_price=100000.0,
        final_decision="PROCEED_TO_SIMULATION",
    )
    assert trade.id is not None
    assert trade.trade_id == "t-001"


def test_trade_get_by_symbol(db_session):
    repo = TradeRepository(db_session)
    repo.create(trade_id="t-002", symbol="ETHUSDT", direction="SHORT", entry_price=3000.0, final_decision="PROCEED_TO_SIMULATION")
    repo.create(trade_id="t-003", symbol="ETHUSDT", direction="LONG", entry_price=3100.0, final_decision="REJECT")
    results = repo.get_by_symbol("ETHUSDT")
    assert len(results) == 2


def test_trade_performance_summary(db_session):
    repo = TradeRepository(db_session)
    repo.create(trade_id="t-004", symbol="BTCUSDT", direction="LONG", entry_price=100.0, final_decision="PROCEED_TO_SIMULATION", pnl=50.0)
    repo.create(trade_id="t-005", symbol="BTCUSDT", direction="LONG", entry_price=100.0, final_decision="PROCEED_TO_SIMULATION", pnl=-20.0)
    summary = repo.get_performance_summary(symbol="BTCUSDT", days=30)
    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1


def test_trade_winrate_by_symbol_and_timeframe(db_session):
    repo = TradeRepository(db_session)
    repo.create(trade_id="t-006", symbol="BTCUSDT", direction="LONG", timeframe="1h", entry_price=100.0, final_decision="PROCEED_TO_SIMULATION", pnl=10.0)
    repo.create(trade_id="t-007", symbol="BTCUSDT", direction="LONG", timeframe="1h", entry_price=100.0, final_decision="PROCEED_TO_SIMULATION", pnl=-5.0)
    result = repo.get_winrate_by_symbol_and_timeframe("BTCUSDT", "1h", days=30)
    assert result["winrate_pct"] == 50.0
    assert result["total_trades"] == 2


# ---------------------------------------------------------------------------
# Position tests
# ---------------------------------------------------------------------------

def test_position_create_and_get_open(db_session):
    repo = PositionRepository(db_session)
    repo.create(trade_id="p-001", symbol="BTCUSDT", direction="LONG", entry_price=100000.0, current_price=100000.0, size=0.1, is_open=True)
    open_positions = repo.get_open()
    assert len(open_positions) == 1
    assert open_positions[0].trade_id == "p-001"


def test_position_close(db_session):
    repo = PositionRepository(db_session)
    repo.create(trade_id="p-002", symbol="ETHUSDT", direction="SHORT", entry_price=3000.0, current_price=3000.0, size=1.0, is_open=True)
    repo.close("p-002", exit_price=2900.0, realized_pnl=100.0)
    pos = repo.get_by_trade_id("p-002")
    assert pos.is_open is False
    assert pos.realized_pnl == 100.0


# ---------------------------------------------------------------------------
# Performance Snapshot tests
# ---------------------------------------------------------------------------

def test_performance_save_and_get_latest(db_session):
    repo = PerformanceRepository(db_session)
    repo.save_snapshot(total_trades=10, winrate_pct=60.0, sharpe_ratio=1.5, total_pnl=500.0)
    latest = repo.get_latest()
    assert latest is not None
    assert latest.total_trades == 10
    assert latest.winrate_pct == 60.0


def test_performance_history(db_session):
    repo = PerformanceRepository(db_session)
    repo.save_snapshot(total_trades=5, winrate_pct=50.0)
    repo.save_snapshot(total_trades=10, winrate_pct=60.0)
    history = repo.get_history(limit=10)
    assert len(history) == 2


# ---------------------------------------------------------------------------
# Strategy Rotation tests
# ---------------------------------------------------------------------------

def test_rotation_create_and_get_recent(db_session):
    repo = StrategyRotationRepository(db_session)
    repo.create(symbol="BTCUSDT", old_strategy="default", new_strategy="pattern_enhanced", regime="INEFFICIENT_TREND", reason="Regime changed")
    rotations = repo.get_recent(limit=10)
    assert len(rotations) == 1
    assert rotations[0].symbol == "BTCUSDT"


# ---------------------------------------------------------------------------
# News Impact tests
# ---------------------------------------------------------------------------

def test_news_impact_create_and_get_by_symbol(db_session):
    repo = NewsImpactRepository(db_session)
    repo.create(symbol="BTCUSDT", source="BBC", title="Bitcoin surges", sentiment_polarity=0.8, urgency=0.6, relevance=0.9, composite_score=0.75)
    items = repo.get_by_symbol("BTCUSDT")
    assert len(items) == 1
    assert items[0].sentiment_polarity == 0.8

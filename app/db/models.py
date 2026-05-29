"""
SQLAlchemy ORM models for the trading system.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, func

from app.db import Base


class Trade(Base):
    """Journal entry persisted in SQL for fast querying."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String, unique=True, index=True, nullable=False)
    signal_id = Column(String, index=True)
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False)
    strategy_id = Column(String, index=True)
    timeframe = Column(String)
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float)
    target_price = Column(Float)
    size = Column(Float)
    confluence_score = Column(Float)
    crisis_score = Column(Float)
    pattern_detected = Column(String, nullable=True)
    pattern_score = Column(Float, default=0.0)
    final_decision = Column(String, nullable=False)
    reject_reason = Column(String, nullable=True)
    pnl = Column(Float, nullable=True)
    fees = Column(Float, default=0.0)
    ai_decision = Column(String)
    ai_confidence = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaperTrade(Base):
    """Paper trading journal — simulated trades against live Kraken prices."""
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String, unique=True, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False)  # LONG / SHORT
    order_type = Column(String, default="market")
    volume = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    fee = Column(Float, default=0.0)
    pnl = Column(Float, nullable=True)
    status = Column(String, default="open")  # open, closed, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class PaperPosition(Base):
    """Aggregated paper position per symbol."""
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False)  # LONG / SHORT
    volume = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    fee_paid = Column(Float, default=0.0)
    status = Column(String, default="open")  # open, closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class PaperBalance(Base):
    """Virtual balance for paper trading."""
    __tablename__ = "paper_balance"

    id = Column(Integer, primary_key=True, index=True)
    currency = Column(String, nullable=False, default="USD")
    balance = Column(Float, nullable=False, default=0.0)
    reserved = Column(Float, default=0.0)
    equity = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Position(Base):
    """Open or closed position tracked in real-time."""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String, unique=True, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, nullable=True)
    strategy_id = Column(String, nullable=True)
    stop_price = Column(Float)
    target_price = Column(Float)
    is_open = Column(Boolean, default=True)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class PerformanceSnapshot(Base):
    """Periodic performance metrics capture."""
    __tablename__ = "performance_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    winrate_pct = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    expectancy = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    lookback_days = Column(Integer, default=30)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())


class StrategyRotation(Base):
    """Log of autonomous loop strategy rotations."""
    __tablename__ = "strategy_rotations"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    old_strategy = Column(String, nullable=False)
    new_strategy = Column(String, nullable=False)
    regime = Column(String)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NewsImpact(Base):
    """Scored news items that affected trading decisions."""
    __tablename__ = "news_impacts"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    source = Column(String)
    title = Column(Text)
    sentiment_polarity = Column(Float)
    urgency = Column(Float)
    relevance = Column(Float)
    composite_score = Column(Float)
    risk_confluence_offset = Column(Float, default=0.0)
    risk_crisis_offset = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

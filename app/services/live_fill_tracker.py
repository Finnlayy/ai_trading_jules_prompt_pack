"""
Live Fill Tracker — tracks open positions in real-time as trades are executed.
Syncs with broker API for divergence detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _normalize_symbol(symbol: str) -> str:
    """Canonicalize symbol for Bybit linear tickers."""
    sym = symbol.upper().strip()
    mapping = {
        "BTCUSD": "BTCUSDT",
        "ETHUSD": "ETHUSDT",
        "SOLUSD": "SOLUSDT",
        "XRPUSD": "XRPUSDT",
        "DOGEUSD": "DOGEUSDT",
        "ADAUSD": "ADAUSDT",
        "AVAXUSD": "AVAXUSDT",
        "LINKUSD": "LINKUSDT",
        "MATICUSD": "MATICUSDT",
        "LTCUSD": "LTCUSDT",
        "DOTUSD": "DOTUSDT",
        "BCHUSD": "BCHUSDT",
    }
    if sym in mapping:
        return mapping[sym]
    if sym.endswith("USD") and not (sym.endswith("USDT") or sym.endswith("USDC")):
        return sym + "T"
    return sym


@dataclass
class FillData:
    entry_price: float
    fill_time: datetime
    size: float
    side: str
    fees: float
    slippage: float


@dataclass
class OpenPosition:
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    realized_pnl: float
    open_time: datetime
    strategy_id: str | None
    stop_price: float
    target_price: float

    @property
    def time_in_trade_minutes(self) -> float:
        return (datetime.now(timezone.utc) - self.open_time).total_seconds() / 60.0


@dataclass
class PositionIntent:
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    size: float | None
    strategy_id: str | None
    decision: str
    ai_trace: dict | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LiveFillTracker:
    """Singleton tracker for live fills and open positions."""

    _instance: LiveFillTracker | None = None

    def __new__(cls) -> LiveFillTracker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._positions: Dict[str, OpenPosition] = {}
        self._intents: Dict[str, PositionIntent] = {}
        self._history: List[dict] = []
        self._persist_path = Path("data/positions.json")
        self._load()

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (UTC)."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _load(self) -> None:
        # Load from JSON file first
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text(encoding="utf-8"))
                for pos_data in data.get("positions", []):
                    pos = OpenPosition(
                        trade_id=pos_data["trade_id"],
                        symbol=_normalize_symbol(pos_data["symbol"]),
                        direction=pos_data["direction"],
                        entry_price=pos_data["entry_price"],
                        current_price=pos_data.get("current_price", pos_data["entry_price"]),
                        size=pos_data["size"],
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0.0),
                        realized_pnl=pos_data.get("realized_pnl", 0.0),
                        open_time=self._ensure_aware(datetime.fromisoformat(pos_data["open_time"])),
                        strategy_id=pos_data.get("strategy_id"),
                        stop_price=pos_data.get("stop_price", 0.0),
                        target_price=pos_data.get("target_price", 0.0),
                    )
                    self._positions[pos.trade_id] = pos
                for intent_data in data.get("intents", []):
                    intent = PositionIntent(
                        trade_id=intent_data["trade_id"],
                        symbol=intent_data["symbol"],
                        direction=intent_data["direction"],
                        entry_price=intent_data["entry_price"],
                        stop_price=intent_data["stop_price"],
                        target_price=intent_data["target_price"],
                        size=intent_data.get("size"),
                        strategy_id=intent_data.get("strategy_id"),
                        decision=intent_data["decision"],
                        ai_trace=intent_data.get("ai_trace"),
                        timestamp=self._ensure_aware(datetime.fromisoformat(intent_data["timestamp"])),
                    )
                    self._intents[intent.trade_id] = intent
            except Exception:
                pass
        # Fallback: load open positions from SQLite (restores after server restart)
        if not self._positions:
            try:
                from app.db import SessionLocal
                from app.db.models import Position as DBPosition
                db = SessionLocal()
                db_positions = db.query(DBPosition).filter(DBPosition.is_open == True).all()
                for dbp in db_positions:
                    pos = OpenPosition(
                        trade_id=dbp.trade_id,
                        symbol=_normalize_symbol(dbp.symbol),
                        direction=dbp.direction,
                        entry_price=dbp.entry_price,
                        current_price=dbp.current_price or dbp.entry_price,
                        size=dbp.size,
                        unrealized_pnl=dbp.unrealized_pnl or 0.0,
                        realized_pnl=dbp.realized_pnl or 0.0,
                        open_time=self._ensure_aware(dbp.opened_at),
                        strategy_id=dbp.strategy_id,
                        stop_price=dbp.stop_price or 0.0,
                        target_price=dbp.target_price or 0.0,
                    )
                    self._positions[pos.trade_id] = pos
                db.close()
            except Exception:
                pass

    def _persist(self) -> None:
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "positions": [
                    {
                        "trade_id": p.trade_id,
                        "symbol": p.symbol,
                        "direction": p.direction,
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "size": p.size,
                        "unrealized_pnl": p.unrealized_pnl,
                        "realized_pnl": p.realized_pnl,
                        "open_time": p.open_time.isoformat(),
                        "strategy_id": p.strategy_id,
                        "stop_price": p.stop_price,
                        "target_price": p.target_price,
                    }
                    for p in self._positions.values()
                ],
                "intents": [
                    {
                        "trade_id": i.trade_id,
                        "symbol": i.symbol,
                        "direction": i.direction,
                        "entry_price": i.entry_price,
                        "stop_price": i.stop_price,
                        "target_price": i.target_price,
                        "size": i.size,
                        "strategy_id": i.strategy_id,
                        "decision": i.decision,
                        "ai_trace": i.ai_trace,
                        "timestamp": i.timestamp.isoformat(),
                    }
                    for i in self._intents.values()
                ],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._persist_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    # -- Public API --------------------------------------------------------

    def record_intent(self, trade_id: str, symbol: str, direction: str,
                      entry_price: float, stop_price: float, target_price: float,
                      decision: str, strategy_id: str | None = None,
                      size: float | None = None, ai_trace: dict | None = None) -> None:
        """Record a trade intent before execution."""
        self._intents[trade_id] = PositionIntent(
            trade_id=trade_id,
            symbol=_normalize_symbol(symbol),
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            size=size,
            strategy_id=strategy_id,
            decision=decision,
            ai_trace=ai_trace,
        )

    def record_fill(self, trade_id: str, fill_data: FillData) -> None:
        """Record a fill and create/update an open position."""
        intent = self._intents.get(trade_id)
        self._positions[trade_id] = OpenPosition(
            trade_id=trade_id,
            symbol=_normalize_symbol(intent.symbol) if intent else "UNKNOWN",
            direction=intent.direction if intent else "LONG",
            entry_price=fill_data.entry_price,
            current_price=fill_data.entry_price,
            size=fill_data.size,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            open_time=fill_data.fill_time,
            strategy_id=intent.strategy_id if intent else None,
            stop_price=intent.stop_price if intent else 0.0,
            target_price=intent.target_price if intent else 0.0,
        )
        self._history.append({
            "event": "fill",
            "trade_id": trade_id,
            "fill_data": {
                "entry_price": fill_data.entry_price,
                "size": fill_data.size,
                "side": fill_data.side,
                "fees": fill_data.fees,
                "slippage": fill_data.slippage,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._persist()
        # Also persist to SQLite
        try:
            from app.db import SessionLocal
            from app.db.models import Position
            db = SessionLocal()
            db.add(Position(
                trade_id=trade_id,
                symbol=intent.symbol if intent else "UNKNOWN",
                direction=intent.direction if intent else "LONG",
                entry_price=fill_data.entry_price,
                current_price=fill_data.entry_price,
                size=fill_data.size,
                unrealized_pnl=0.0,
                realized_pnl=None,
                strategy_id=intent.strategy_id if intent else None,
                stop_price=intent.stop_price if intent else 0.0,
                target_price=intent.target_price if intent else 0.0,
                is_open=True,
                opened_at=fill_data.fill_time,
            ))
            db.commit()
            db.close()
        except Exception:
            pass

    def record_exit(self, trade_id: str, exit_price: float,
                    exit_time: datetime | None = None) -> None:
        """Close a position and record realized PnL."""
        pos = self._positions.pop(trade_id, None)
        if pos is None:
            return
        exit = exit_time or datetime.now(timezone.utc)
        if pos.direction == "LONG":
            pnl = (exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - exit_price) * pos.size
        pos.realized_pnl = pnl
        pos.current_price = exit_price
        self._history.append({
            "event": "exit",
            "trade_id": trade_id,
            "exit_price": exit_price,
            "realized_pnl": pnl,
            "timestamp": exit.isoformat(),
        })
        self._persist()
        # Record outcome in ConfidenceRegistry for learning loop
        try:
            from app.services.confidence_registry import confidence_registry
            pnl_pct = (pnl / (pos.entry_price * pos.size)) * 100.0 if pos.entry_price and pos.size else 0.0
            risk = abs(pos.entry_price - pos.stop_price) if pos.stop_price else abs(pnl_pct)
            rr = abs(pnl_pct / risk) if risk else 0.0
            win = pnl > 0
            confidence_registry.record_trade_outcome(
                symbol=pos.symbol,
                direction=pos.direction,
                pnl_pct=pnl_pct,
                rr=rr,
                win=win,
            )
            # Record scout outcomes if ai_trace is available
            intent = self._intents.pop(trade_id, None)
            if intent and intent.ai_trace:
                scout_decisions = intent.ai_trace.get("scouts", {})
                for scout_name, scout_report in scout_decisions.items():
                    scout_approved = isinstance(scout_report, dict) and scout_report.get("decision") == "PROCEED_TO_SIMULATION"
                    if not scout_approved and isinstance(scout_report, str):
                        scout_approved = "PROCEED" in scout_report.upper() or "APPROVE" in scout_report.upper()
                    was_correct = (scout_approved and win) or (not scout_approved and not win)
                    confidence_registry.mark_scout_outcome(
                        symbol=pos.symbol,
                        scout_names=[scout_name],
                        was_correct=was_correct,
                    )
        except Exception:
            pass
        # Also update SQLite
        try:
            from app.db import SessionLocal
            from app.db.models import Position
            db = SessionLocal()
            db_pos = db.query(Position).filter(Position.trade_id == trade_id).first()
            if db_pos:
                db_pos.is_open = False
                db_pos.current_price = exit_price
                db_pos.realized_pnl = pnl
                db_pos.closed_at = exit
                db.commit()
            db.close()
        except Exception:
            pass

    def update_price(self, trade_id: str, current_price: float) -> None:
        """Update current price and unrealized PnL for a position."""
        pos = self._positions.get(trade_id)
        if pos is None:
            return
        pos.current_price = current_price
        if pos.direction == "LONG":
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size
        else:
            pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size

    def get_open_positions(self) -> List[OpenPosition]:
        return list(self._positions.values())

    def get_position(self, trade_id: str) -> OpenPosition | None:
        return self._positions.get(trade_id)

    def get_daily_pnl(self) -> float:
        """Sum of realized PnL from today's exits."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        total = 0.0
        for h in self._history:
            if h["event"] == "exit" and h["timestamp"].startswith(today):
                total += h.get("realized_pnl", 0.0)
        return total

    def sync_with_broker(self, broker_positions: List[dict]) -> dict:
        """Detect divergence between local ledger and broker positions."""
        broker_ids = {p.get("trade_id") for p in broker_positions}
        local_ids = set(self._positions.keys())
        missing_in_local = broker_ids - local_ids
        missing_in_broker = local_ids - broker_ids
        return {
            "divergence": bool(missing_in_local or missing_in_broker),
            "missing_in_local": list(missing_in_local),
            "missing_in_broker": list(missing_in_broker),
            "matched": len(broker_ids & local_ids),
        }

    def reset(self) -> None:
        self._positions.clear()
        self._intents.clear()
        self._history.clear()
        self._persist()


# Global singleton
live_fill_tracker = LiveFillTracker()

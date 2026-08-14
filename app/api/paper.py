from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.api.orchestrator import _get_broker
from app.core.config import BROKER_MODE
from app.schemas.paper import PaperReplayRequest, PaperSessionStartRequest
from app.services.shadow_paper_engine import shadow_paper_engine

router = APIRouter()


class PaperSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}

    def snapshot(self, session_id: str) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError(session_id)
        data = {key: value for key, value in session.items() if key != "task"}
        data["seen_signal_count"] = len(session.get("seen_signal_ids", set()))
        data["seen_signal_ids"] = sorted(session.get("seen_signal_ids", set()))
        return data

    async def start(
        self,
        *,
        symbol: str,
        timeframe: str,
        bars: int,
        max_signals: Optional[int],
        min_confluence: Optional[float],
        max_holding_bars: int,
        use_ai: bool,
        poll_interval_seconds: float,
        run_once: bool,
    ) -> dict[str, Any]:
        session_id = f"paper-{uuid.uuid4().hex[:10]}"
        session = {
            "session_id": session_id,
            "status": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": bars,
            "max_signals": max_signals,
            "min_confluence": min_confluence,
            "max_holding_bars": max_holding_bars,
            "use_ai": use_ai,
            "poll_interval_seconds": poll_interval_seconds,
            "run_once": run_once,
            "seen_signal_ids": set(),
            "results": [],
            "last_replay": None,
            "error": None,
        }
        self.sessions[session_id] = session
        session["task"] = asyncio.create_task(self._run(session_id))
        return self.snapshot(session_id)

    async def stop(self, session_id: str) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError(session_id)
        task = session.get("task")
        if task and not task.done():
            task.cancel()
        session["status"] = "stopped"
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self.snapshot(session_id)

    async def _run(self, session_id: str) -> None:
        session = self.sessions[session_id]
        while True:
            try:
                session["status"] = "running"
                req = PaperReplayRequest(
                    symbol=session["symbol"],
                    timeframe=session["timeframe"],
                    bars=session["bars"],
                    max_signals=session["max_signals"],
                    min_confluence=session["min_confluence"],
                    max_holding_bars=session["max_holding_bars"],
                    use_ai=session["use_ai"],
                )
                replay = await shadow_paper_engine.replay(req)
                seen = session["seen_signal_ids"]
                fresh = []
                for row in replay.get("results", []):
                    signal_id = row.get("signal_id")
                    if not signal_id or signal_id in seen:
                        continue
                    seen.add(signal_id)
                    fresh.append(row)
                session["results"] = [*fresh, *session["results"]][:250]
                session["last_replay"] = {
                    key: value for key, value in replay.items() if key != "results"
                }
                session["updated_at"] = datetime.now(timezone.utc).isoformat()
                session["error"] = None
                if session["run_once"]:
                    session["status"] = "completed"
                    return
                await asyncio.sleep(session["poll_interval_seconds"])
            except asyncio.CancelledError:
                session["status"] = "stopped"
                session["updated_at"] = datetime.now(timezone.utc).isoformat()
                return
            except Exception as exc:
                session["status"] = "error"
                session["error"] = str(exc)
                session["updated_at"] = datetime.now(timezone.utc).isoformat()
                return


paper_sessions = PaperSessionStore()


def _pionex_context() -> dict[str, Any]:
    broker = _get_broker()
    context: dict[str, Any] = {
        "broker_mode": BROKER_MODE,
        "broker_type": getattr(
            broker, "get_broker_type", lambda: type(broker).__name__
        )(),
        "display_mode": getattr(broker, "get_broker_mode", lambda: "unknown")(),
        "connected": getattr(broker, "is_ready", lambda: False)(),
        "live_capable": getattr(broker, "is_live_capable", lambda: False)(),
        "order_routing": "disabled_in_paper_mode",
    }
    if context["connected"] and hasattr(broker, "get_wallet_balances"):
        wallets = {}
        for key, account_mode in (("primary", "SPOT"), ("futures", "FUTURES")):
            try:
                wallets[key] = broker.get_wallet_balances(account_mode=account_mode)
            except Exception as exc:
                wallets[key] = {"account_mode": account_mode, "error": str(exc)}
        context["wallets"] = wallets
    if context["connected"] and hasattr(broker, "get_positions"):
        try:
            context["positions"] = broker.get_positions()
        except Exception as exc:
            context["positions"] = {"error": str(exc), "positions": []}
    return context


@router.post("/replay")
async def replay_paper(req: PaperReplayRequest) -> dict[str, Any]:
    try:
        replay = await shadow_paper_engine.replay(req)
        replay["pionex_context"] = _pionex_context()
        return replay
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/session/start")
async def start_paper_session(req: PaperSessionStartRequest) -> dict[str, Any]:
    if req.poll_interval_seconds < 5:
        raise HTTPException(
            status_code=422, detail="poll_interval_seconds must be >= 5"
        )
    return await paper_sessions.start(
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars=req.bars,
        max_signals=req.max_signals,
        min_confluence=req.min_confluence,
        max_holding_bars=req.max_holding_bars,
        use_ai=req.use_ai,
        poll_interval_seconds=req.poll_interval_seconds,
        run_once=req.run_once,
    )


@router.get("/session/status")
async def paper_session_status(session_id: str | None = None) -> dict[str, Any]:
    if session_id:
        try:
            return paper_sessions.snapshot(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Paper session not found")
    return {
        "sessions": [
            paper_sessions.snapshot(item)
            for item in sorted(paper_sessions.sessions.keys())
        ]
    }


@router.post("/session/stop")
async def stop_paper_session(session_id: str) -> dict[str, Any]:
    try:
        return await paper_sessions.stop(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Paper session not found")


@router.get("/config")
def get_paper_config():
    """Fetch paper trading and regime engine settings."""
    import app.core.config as config
    from app.services.regime_engine import regime_engine_instance
    return {
        "PAPER_TRADING_RELAX_RISK": config.PAPER_TRADING_RELAX_RISK,
        "REGIME_ALLOW_RW1_SIGNALS": regime_engine_instance.allow_rw1_signals,
    }


@router.post("/config")
def update_paper_config(settings: dict):
    """Update paper trading and regime engine settings in-memory."""
    import app.core.config as config
    from app.services.regime_engine import regime_engine_instance
    
    if "PAPER_TRADING_RELAX_RISK" in settings:
        config.PAPER_TRADING_RELAX_RISK = bool(settings["PAPER_TRADING_RELAX_RISK"])
    if "REGIME_ALLOW_RW1_SIGNALS" in settings:
        val = bool(settings["REGIME_ALLOW_RW1_SIGNALS"])
        config.REGIME_ALLOW_RW1_SIGNALS = val
        regime_engine_instance.allow_rw1_signals = val
        
    return {
        "status": "success",
        "PAPER_TRADING_RELAX_RISK": config.PAPER_TRADING_RELAX_RISK,
        "REGIME_ALLOW_RW1_SIGNALS": regime_engine_instance.allow_rw1_signals,
    }


@router.get("/shadow-queue")
def get_shadow_queue_entries(limit: int = 100):
    """Fetch rejected signal entries tracked in the shadow queue."""
    from app.services.shadow_queue import shadow_queue
    entries = shadow_queue._load()
    result = []
    for e in reversed(entries):
        result.append({
            "signal_id": e.signal_id,
            "timestamp": e.timestamp,
            "symbol": e.symbol,
            "timeframe": e.timeframe,
            "direction": e.direction,
            "entry_price": e.entry_price,
            "stop_price": e.stop_price,
            "target_price": e.target_price,
            "scout_decisions": e.scout_decisions,
            "added_at": e.added_at,
            "evaluated": e.evaluated,
        })
    return {
        "status": "ok",
        "entries": result[:limit],
        "count": len(entries),
        "pending_count": sum(1 for e in entries if not e.evaluated),
        "evaluated_count": sum(1 for e in entries if e.evaluated),
    }


@router.get("/workers/status")
def get_workers_status():
    """Fetch active background task worker statuses."""
    from app.services.webhook_consumer import webhook_consumer_instance
    from app.services.position_monitor import paper_position_monitor_instance
    from app.services.training_loop import training_loop
    
    return {
        "webhook_consumer": {
            "is_running": getattr(webhook_consumer_instance, "is_running", True),
            "queue_size": webhook_consumer_instance.queue.qsize() if hasattr(webhook_consumer_instance, "queue") else 0,
        },
        "position_monitor": {
            "is_running": getattr(paper_position_monitor_instance, "is_running", True),
        },
        "training_loop": {
            "is_running": getattr(training_loop, "is_running", False),
            "interval_seconds": getattr(training_loop, "interval_seconds", None),
        }
    }


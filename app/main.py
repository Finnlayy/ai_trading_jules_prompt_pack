import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.api.ai_layer import router as ai_layer_router
from fastapi.responses import FileResponse
from app.api.backtest_runner import router as backtest_router
from app.api.endpoints import router as m8_router
from app.api.market_data import router as market_router
from app.api.recommendations import router as recommend_router
from app.api.confidence_registry import router as confidence_router
from app.api.circuit_breaker import router as circuit_breaker_router
from app.api.reconciliation import router as reconciliation_router
from app.api.news import router as news_router

app = FastAPI(
    title="Agent-Reflex Hybrid Trader API",
    description="Simulation-first trading API. Open this UI to inspect health, backtest, and M8 webhook routes.",
)

app.include_router(m8_router, prefix="/webhook", tags=["webhook"])
app.include_router(backtest_router, prefix="/backtest", tags=["backtest"])
app.include_router(ai_layer_router, prefix="/ai", tags=["ai-layer"])
app.include_router(market_router, prefix="/market", tags=["market-data"])
app.include_router(recommend_router, prefix="/market", tags=["market-data"])
app.include_router(confidence_router, prefix="/confidence", tags=["confidence-registry"])
app.include_router(circuit_breaker_router, prefix="/circuit", tags=["circuit-breaker"])
app.include_router(reconciliation_router, prefix="/reconcile", tags=["reconciliation"])
app.include_router(news_router, prefix="/news", tags=["news"])

@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(Path(__file__).resolve().parents[1] / "frontend.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ------------------------------------------------------------------
# Background heartbeat task
# ------------------------------------------------------------------
_heartbeat_task = None
_startup_time = datetime.now(timezone.utc)


async def _heartbeat_loop():
    """Send Telegram heartbeat every hour."""
    from app.services.portfolio_circuit_breaker import circuit_breaker_instance
    from app.services.risk_engine import risk_engine_instance
    from app.api.orchestrator import broker_instance

    # Wait a bit for app to fully start
    await asyncio.sleep(60)

    while True:
        try:
            notifier = getattr(broker_instance, "notifier", None)
            if notifier and getattr(notifier, "send_heartbeat", None):
                uptime = (datetime.now(timezone.utc) - _startup_time).total_seconds() // 60
                circuit = circuit_breaker_instance.check_trade_allowed()
                notifier.send_heartbeat(
                    int(uptime),
                    risk_engine_instance.trades_today,
                    circuit,
                )
        except Exception:
            pass
        await asyncio.sleep(3600)  # every hour


@app.on_event("startup")
def startup_event():
    global _heartbeat_task
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())


@app.on_event("shutdown")
def shutdown_event():
    global _heartbeat_task
    if _heartbeat_task:
        _heartbeat_task.cancel()

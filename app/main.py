import asyncio
from datetime import datetime, timezone
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from app.api.ai_layer import router as ai_layer_router
from app.api.backtest_runner import router as backtest_router
from app.api.endpoints import router as m8_router
from app.api.market_data import router as market_router
from app.api.recommendations import router as recommend_router
from app.api.confidence_registry import router as confidence_router
from app.api.circuit_breaker import router as circuit_breaker_router
from app.api.reconciliation import router as reconciliation_router
from app.api.news import router as news_router
from app.api.broker import router as broker_router
from app.api.paper import router as paper_router
from app.api.strategies import router as strategies_router
from app.api.patterns import router as patterns_router
from app.api.news_impact import router as news_impact_router
from app.api.autonomous_loop import router as autonomous_loop_router
from app.api.live_trading import router as live_trading_router
from app.api.db_insight import router as db_insight_router
from app.api.academy import router as academy_router
from app.api.ctrader import router as ctrader_router

app = FastAPI(
    title="Agent-Reflex Hybrid Trader API",
    description="Simulation-first trading API. Open this UI to inspect health, backtest, and M8 webhook routes.",
)

ROOT_DIR = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=ROOT_DIR / "app" / "static"), name="static")

app.include_router(m8_router, prefix="/webhook", tags=["webhook"])
app.include_router(backtest_router, prefix="/backtest", tags=["backtest"])
app.include_router(ai_layer_router, prefix="/ai", tags=["ai-layer"])
app.include_router(market_router, prefix="/market", tags=["market-data"])
app.include_router(recommend_router, prefix="/market", tags=["market-data"])
app.include_router(confidence_router, prefix="/confidence", tags=["confidence-registry"])
app.include_router(circuit_breaker_router, prefix="/circuit", tags=["circuit-breaker"])
app.include_router(reconciliation_router, prefix="/reconcile", tags=["reconciliation"])
app.include_router(news_router, prefix="/news", tags=["news"])
app.include_router(broker_router, prefix="/broker", tags=["broker"])
app.include_router(paper_router, prefix="/paper", tags=["paper"])
app.include_router(strategies_router, prefix="/strategies", tags=["strategies"])
app.include_router(patterns_router, prefix="/patterns", tags=["patterns"])
app.include_router(news_impact_router, prefix="/news", tags=["news-impact"])
app.include_router(autonomous_loop_router, prefix="/loop", tags=["autonomous_loop"])
app.include_router(live_trading_router, prefix="/live", tags=["live_trading"])
app.include_router(db_insight_router, prefix="/db", tags=["db-insight"])
app.include_router(academy_router, tags=["academy"])
app.include_router(ctrader_router, prefix="/ctrader", tags=["ctrader"])

@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(ROOT_DIR / "frontend.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

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
            logger.exception("Error in heartbeat loop")
        await asyncio.sleep(3600)  # every hour


async def _news_poll_loop():
    """Periodically fetch news from RSS feeds."""
    from app.services.news_aggregator import news_aggregator_instance
    from app.core.config import NEWS_POLL_INTERVAL_MINUTES

    # Initial fetch after short delay
    await asyncio.sleep(10)

    while True:
        try:
            await news_aggregator_instance.fetch(source="all")
        except Exception:
            pass
        await asyncio.sleep(NEWS_POLL_INTERVAL_MINUTES * 60)


async def _autonomous_loop_auto_start():
    """Optionally auto-start the autonomous trading loop after startup."""
    from app.core.config import AUTONOMOUS_LOOP_AUTO_START
    from app.services.autonomous_loop import autonomous_loop_instance

    await asyncio.sleep(15)
    if AUTONOMOUS_LOOP_AUTO_START:
        try:
            autonomous_loop_instance.start()
        except Exception:
            pass


_news_poll_task = None
_autostart_task = None
_price_poller_task = None
_shadow_queue_task = None


async def _shadow_queue_loop():
    """Periodically process pending shadow-queue entries for rejected-trade learning."""
    from app.services.shadow_queue import shadow_queue
    while True:
        try:
            await asyncio.sleep(300)  # every 5 minutes
            await shadow_queue.process_pending()
            shadow_queue.purge_old(max_age_days=7)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@app.on_event("startup")
def startup_event():
    global _heartbeat_task, _news_poll_task, _autostart_task, _price_poller_task, _shadow_queue_task
    # Create DB tables
    from app.db import Base, engine
    Base.metadata.create_all(bind=engine)
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    _news_poll_task = asyncio.create_task(_news_poll_loop())
    _autostart_task = asyncio.create_task(_autonomous_loop_auto_start())
    # Start price poller for live position monitoring
    from app.services.price_poller import price_poller
    price_poller.start()
    # Start shadow queue processor for rejected-trade feedback
    _shadow_queue_task = asyncio.create_task(_shadow_queue_loop())


@app.on_event("shutdown")
def shutdown_event():
    global _heartbeat_task, _news_poll_task, _autostart_task, _price_poller_task, _shadow_queue_task
    from app.services.autonomous_loop import autonomous_loop_instance
    from app.services.price_poller import price_poller
    autonomous_loop_instance.stop()
    price_poller.stop()
    if _heartbeat_task:
        _heartbeat_task.cancel()
    if _news_poll_task:
        _news_poll_task.cancel()
    if _autostart_task:
        _autostart_task.cancel()
    if _shadow_queue_task:
        _shadow_queue_task.cancel()

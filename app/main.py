import logging

logger = logging.getLogger(__name__)

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from app.api.auth import router as auth_router, get_current_user
from fastapi import Depends
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
from app.api.ctrader_fix import router as ctrader_fix_router
from app.api.kraken import router as kraken_router
from app.api.kraken_paper import router as kraken_paper_router
from app.api.lifecycle import router as lifecycle_router
from app.api.webhook_signal import router as webhook_signal_router
from app.api.perception import router as perception_router
from app.api.agentic import router as agentic_router
from app.api.simulator import router as simulator_router
from app.services.webhook_consumer import webhook_consumer_instance
from app.services.position_monitor import paper_position_monitor_instance

app = FastAPI(
    title="Agent-Reflex Hybrid Trader API",
    description="Simulation-first trading API. Open this UI to inspect health, backtest, and M8 webhook routes.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ROOT_DIR = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=ROOT_DIR / "app" / "static"), name="static")

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(m8_router, prefix="/webhook", tags=["webhook"])
app.include_router(backtest_router, prefix="/backtest", tags=["backtest"], dependencies=[Depends(get_current_user)])
app.include_router(ai_layer_router, prefix="/ai", tags=["ai-layer"], dependencies=[Depends(get_current_user)])
app.include_router(market_router, prefix="/market", tags=["market-data"], dependencies=[Depends(get_current_user)])
app.include_router(recommend_router, prefix="/market", tags=["market-data"], dependencies=[Depends(get_current_user)])
app.include_router(confidence_router, prefix="/confidence", tags=["confidence-registry"], dependencies=[Depends(get_current_user)])
app.include_router(circuit_breaker_router, prefix="/circuit", tags=["circuit-breaker"], dependencies=[Depends(get_current_user)])
app.include_router(reconciliation_router, prefix="/reconcile", tags=["reconciliation"], dependencies=[Depends(get_current_user)])
app.include_router(news_router, prefix="/news", tags=["news"], dependencies=[Depends(get_current_user)])
app.include_router(broker_router, prefix="/broker", tags=["broker"], dependencies=[Depends(get_current_user)])
app.include_router(paper_router, prefix="/paper", tags=["paper"], dependencies=[Depends(get_current_user)])
app.include_router(strategies_router, prefix="/strategies", tags=["strategies"], dependencies=[Depends(get_current_user)])
app.include_router(patterns_router, prefix="/patterns", tags=["patterns"], dependencies=[Depends(get_current_user)])
app.include_router(news_impact_router, prefix="/news", tags=["news-impact"], dependencies=[Depends(get_current_user)])
app.include_router(autonomous_loop_router, prefix="/loop", tags=["autonomous_loop"], dependencies=[Depends(get_current_user)])
app.include_router(live_trading_router, prefix="/live", tags=["live_trading"], dependencies=[Depends(get_current_user)])
app.include_router(db_insight_router, prefix="/db", tags=["db-insight"], dependencies=[Depends(get_current_user)])
app.include_router(academy_router, tags=["academy"], dependencies=[Depends(get_current_user)])
app.include_router(ctrader_router, prefix="/ctrader", tags=["ctrader"], dependencies=[Depends(get_current_user)])
app.include_router(ctrader_fix_router, prefix="/ctrader-fix", tags=["ctrader-fix"], dependencies=[Depends(get_current_user)])
app.include_router(kraken_router, tags=["kraken"], dependencies=[Depends(get_current_user)])
app.include_router(kraken_paper_router, tags=["kraken-paper"], dependencies=[Depends(get_current_user)])
app.include_router(lifecycle_router, prefix="/lifecycle", tags=["lifecycle"], dependencies=[Depends(get_current_user)])
app.include_router(webhook_signal_router, tags=["webhook"])

app.include_router(perception_router, prefix="/perception", tags=["perception"], dependencies=[Depends(get_current_user)])
app.include_router(agentic_router, prefix="/agentic", tags=["agentic"], dependencies=[Depends(get_current_user)])
app.include_router(simulator_router, prefix="/simulator", tags=["simulator"], dependencies=[Depends(get_current_user)])

# Fallback dummy routers if merged routes were lost
try:
    from app.api.auth import router as auth_router
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
except ImportError:
    pass
try:
    from app.api.stream_manager import router as stream_manager_router
    app.include_router(stream_manager_router, prefix="/stream", tags=["stream"])
except ImportError:
    pass



@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

from app.api.auth import get_api_key

@app.get("/health")
def health_check(api_key: str | None = Depends(get_api_key)):
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


async def _training_loop_auto_start():
    """Optionally auto-start the academy training loop after startup."""
    from app.core.config import TRAINING_LOOP_AUTO_START
    from app.services.training_loop import training_loop

    await asyncio.sleep(5)
    if TRAINING_LOOP_AUTO_START:
        try:
            await training_loop.start()
        except Exception:
            pass


_news_poll_task = None
_autostart_task = None
_training_autostart_task = None
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
    # Create DB tables
    from app.db import Base, engine
    Base.metadata.create_all(bind=engine)
    global _heartbeat_task; _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    global _news_poll_task; _news_poll_task = asyncio.create_task(_news_poll_loop())
    global _autostart_task; _autostart_task = asyncio.create_task(_autonomous_loop_auto_start())
    global _training_autostart_task; _training_autostart_task = asyncio.create_task(_training_loop_auto_start())
    # Start price poller for live position monitoring
    from app.services.price_poller import price_poller
    price_poller.start()
    # Start shadow queue processor for rejected-trade feedback
    global _shadow_queue_task; _shadow_queue_task = asyncio.create_task(_shadow_queue_loop())
    # Start webhook consumer for autonomous signal → paper order execution
    webhook_consumer_instance.start()
    # Start position monitor for auto SL/TP
    paper_position_monitor_instance.start()


@app.on_event("shutdown")
def shutdown_event():
    from app.services.autonomous_loop import autonomous_loop_instance
    from app.services.price_poller import price_poller
    from app.services.training_loop import training_loop
    autonomous_loop_instance.stop()
    training_loop.stop_now()
    webhook_consumer_instance.stop()
    paper_position_monitor_instance.stop()
    price_poller.stop()
    if _heartbeat_task:
        _heartbeat_task.cancel()
    if _news_poll_task:
        _news_poll_task.cancel()
    if _autostart_task:
        _autostart_task.cancel()
    if _training_autostart_task:
        _training_autostart_task.cancel()
    if _shadow_queue_task:
        _shadow_queue_task.cancel()

app.mount("/", StaticFiles(directory=ROOT_DIR / "frontend" / "dist", html=True), name="vite_spa")

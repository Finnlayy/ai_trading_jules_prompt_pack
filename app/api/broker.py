"""Broker API endpoints for status, health, and mode selection."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.orchestrator import broker_instance, reset_broker
from app.services.broker_factory import BrokerFactory
from app.core.config import BROKER_MODE

router = APIRouter()


@router.get("/status")
async def get_broker_status():
    """Return current broker status, health, and configuration."""
    broker = broker_instance
    health = getattr(broker, "health", lambda: {})()

    # Extract execution safety metadata
    allowed_symbols = []
    default_spot = None
    min_order = 5.0
    max_order = 100.0

    if hasattr(broker, "config"):
        allowed_symbols = getattr(broker.config, "allowed_symbols", []) or []
        default_spot = getattr(broker.config, "default_spot_symbol", None)

    if hasattr(broker, "kelly_sizer") and hasattr(broker.kelly_sizer, "config"):
        min_order = getattr(broker.kelly_sizer.config, "min_order_usdt", 5.0)
        max_order = getattr(broker.kelly_sizer.config, "max_order_usdt", 100.0)

    is_live = getattr(broker, "is_live_capable", lambda: False)()

    return {
        "status": "ok",
        "broker_mode": BROKER_MODE,
        "broker_name": getattr(broker, "get_broker_name", lambda: "unknown")(),
        "broker_type": getattr(broker, "get_broker_type", lambda: "unknown")(),
        "broker_mode_display": getattr(broker, "get_broker_mode", lambda: "unknown")(),
        "live_capable": is_live,
        "ready": getattr(broker, "is_ready", lambda: False)(),
        "health": health,
        "live_enabled": is_live,
        "allowed_symbols": list(allowed_symbols),
        "default_spot_symbol": default_spot,
        "min_order_usdt": min_order,
        "max_order_usdt": max_order,
        "requires_ui_confirmation": is_live,
    }


@router.get("/modes")
async def get_available_modes():
    """Return all available broker modes for the UI selector."""
    return {
        "status": "ok",
        "current": BROKER_MODE,
        "available": [
            {"value": mode, "label": BrokerFactory.mode_display_name(mode)}
            for mode in BrokerFactory.available_modes()
        ],
    }


@router.post("/reset")
async def reset_broker_endpoint():
    """Reset the broker instance (e.g. after config change)."""
    new_broker = reset_broker()
    return {
        "status": "ok",
        "broker": getattr(new_broker, "get_broker_name", lambda: "unknown")(),
        "mode": getattr(new_broker, "get_broker_mode", lambda: "unknown")(),
    }

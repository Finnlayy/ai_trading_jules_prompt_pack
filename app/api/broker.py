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
    return {
        "status": "ok",
        "broker_mode": BROKER_MODE,
        "broker_name": getattr(broker, "get_broker_name", lambda: "unknown")(),
        "broker_type": getattr(broker, "get_broker_type", lambda: "unknown")(),
        "broker_mode_display": getattr(broker, "get_broker_mode", lambda: "unknown")(),
        "live_capable": getattr(broker, "is_live_capable", lambda: False)(),
        "ready": getattr(broker, "is_ready", lambda: False)(),
        "health": health,
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

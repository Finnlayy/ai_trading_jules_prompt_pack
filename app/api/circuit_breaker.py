"""
API endpoints for the Portfolio Circuit Breaker.
"""

from fastapi import APIRouter
from typing import Any

from app.services.portfolio_circuit_breaker import circuit_breaker_instance

router = APIRouter()


@router.get("/status", tags=["circuit-breaker"])
async def get_circuit_status() -> dict[str, Any]:
    """Return current circuit breaker state."""
    return circuit_breaker_instance.check_trade_allowed()


@router.get("/state", tags=["circuit-breaker"])
async def get_circuit_state() -> dict[str, Any]:
    """Return full circuit breaker state dump."""
    return circuit_breaker_instance.get_state()


@router.post("/reset", tags=["circuit-breaker"])
async def reset_circuit() -> dict[str, str]:
    """Reset the circuit breaker for the current day."""
    circuit_breaker_instance.reset()
    return {"status": "ok", "message": "Circuit breaker reset"}

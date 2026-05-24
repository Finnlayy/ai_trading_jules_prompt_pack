"""
API endpoints for the Confidence Registry.
Allows viewing per-symbol scout stats and resetting the registry.
"""

from fastapi import APIRouter
from typing import Any

from app.services.confidence_registry import confidence_registry

router = APIRouter()


@router.get("/stats", tags=["confidence-registry"])
async def get_confidence_stats() -> dict[str, Any]:
    """Return all per-symbol, per-scout confidence statistics."""
    return confidence_registry.dump()


@router.get("/stats/{symbol}", tags=["confidence-registry"])
async def get_symbol_confidence(symbol: str) -> dict[str, Any]:
    """Return confidence stats for a specific symbol."""
    stats = confidence_registry.get_symbol_stats(symbol)
    return confidence_registry._serialize_symbol(stats)


@router.get("/context/{symbol}", tags=["confidence-registry"])
async def get_symbol_context(symbol: str, direction: str = "LONG") -> dict[str, str]:
    """Return the injected context string for a symbol+direction."""
    return {
        "symbol": symbol.upper(),
        "direction": direction.upper(),
        "context": confidence_registry.get_symbol_context(symbol, direction),
    }


@router.post("/reset/{symbol}", tags=["confidence-registry"])
async def reset_symbol(symbol: str) -> dict[str, str]:
    """Reset confidence stats for a single symbol."""
    confidence_registry.reset_symbol(symbol)
    return {"status": "ok", "message": f"Reset confidence stats for {symbol.upper()}"}


@router.post("/reset", tags=["confidence-registry"])
async def reset_all() -> dict[str, str]:
    """Reset all confidence stats."""
    confidence_registry.reset_all()
    return {"status": "ok", "message": "Reset all confidence stats"}

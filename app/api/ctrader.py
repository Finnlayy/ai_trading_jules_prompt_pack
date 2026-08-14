"""cTrader broker control and inspection endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.schemas.ctrader import (
    CTraderAccountsResponse,
    CTraderActionResponse,
    CTraderBalanceResponse,
    CTraderOrderRequest,
    CTraderOrderResponse,
    CTraderPositionsResponse,
    CTraderStatusResponse,
    CTraderSymbolsResponse,
)
from app.services.ctrader_broker import CTraderBroker
from app.services.journal_logger import journal_logger_instance

router = APIRouter()

_ctrader_broker_instance: CTraderBroker | None = None


def _active_ctrader_broker() -> CTraderBroker | None:
    from app.api import orchestrator

    broker = orchestrator.broker_instance
    broker_type = getattr(broker, "get_broker_type", lambda: "")()
    if broker_type == "ctrader":
        return broker
    return None


def _get_ctrader_broker() -> CTraderBroker:
    global _ctrader_broker_instance
    active = _active_ctrader_broker()
    if active is not None:
        return active
    if _ctrader_broker_instance is None:
        _ctrader_broker_instance = CTraderBroker(journal_path=journal_logger_instance.filepath)
    return _ctrader_broker_instance


@router.get("/status", response_model=CTraderStatusResponse)
async def get_ctrader_status():
    """Return cTrader connection, auth, and configuration status."""
    broker = _get_ctrader_broker()
    return await asyncio.to_thread(broker.health)


@router.get("/symbols", response_model=CTraderSymbolsResponse)
async def get_ctrader_symbols():
    """Return the cached cTrader symbol map."""
    broker = _get_ctrader_broker()
    symbols = await asyncio.to_thread(broker.get_symbols)
    return CTraderSymbolsResponse(count=len(symbols), symbols=symbols)


@router.post("/symbols/refresh", response_model=CTraderSymbolsResponse)
async def refresh_ctrader_symbols():
    """Force-refresh the cTrader symbol map from Open API."""
    broker = _get_ctrader_broker()
    try:
        symbols = await asyncio.to_thread(broker.refresh_symbols)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CTraderSymbolsResponse(
        count=len(symbols),
        symbols=symbols,
        refreshed_at=datetime.now(timezone.utc),
    )


@router.get("/positions", response_model=CTraderPositionsResponse)
async def get_ctrader_positions():
    """Return cTrader open positions."""
    broker = _get_ctrader_broker()
    result = await asyncio.to_thread(broker.get_positions)
    return CTraderPositionsResponse(
        status=result.get("status", "ok"),
        positions=result.get("positions", []),
        error=result.get("error"),
    )


@router.get("/balance", response_model=CTraderBalanceResponse)
async def get_ctrader_balance():
    """Return cTrader account balance and margin data."""
    broker = _get_ctrader_broker()
    return await asyncio.to_thread(broker.get_wallet_balances, "CTRADER")


@router.post("/connect", response_model=CTraderActionResponse)
async def connect_ctrader():
    """Manually trigger cTrader connection and authentication."""
    broker = _get_ctrader_broker()
    try:
        health = await asyncio.to_thread(broker.connect)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CTraderActionResponse(health=health)


@router.post("/disconnect", response_model=CTraderActionResponse)
async def disconnect_ctrader():
    """Gracefully stop the cTrader client connection."""
    broker = _get_ctrader_broker()
    health = await asyncio.to_thread(broker.disconnect)
    return CTraderActionResponse(health=health)


@router.post("/order", response_model=CTraderOrderResponse)
async def place_ctrader_order(req: CTraderOrderRequest):
    """Place a direct market order through cTrader Open API."""
    broker = _get_ctrader_broker()
    result = await asyncio.to_thread(
        broker.place_direct_order,
        req=req,
    )
    return CTraderOrderResponse(**result)


@router.get("/accounts", response_model=CTraderAccountsResponse)
async def list_ctrader_accounts():
    """
    List available cTrader accounts for the configured app credentials.
    Useful for discovering the Account ID (ctidTraderAccountId) to put in .env.
    """
    broker = _get_ctrader_broker()
    try:
        accounts = await asyncio.to_thread(broker.list_accounts)
    except Exception as exc:
        return CTraderAccountsResponse(
            status="error",
            accounts=[],
            error=str(exc),
            setup_guide=(
                "1. Go to https://ctrader-open-api.ctrader.com/ and create an app.\n"
                "2. Copy Client ID and Client Secret into .env (CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET).\n"
                "3. In cTrader app: Settings → Open API → Generate Token for your demo account.\n"
                "4. Copy the Access Token into .env (CTRADER_ACCESS_TOKEN).\n"
                "5. Use this endpoint or check cTrader app for the Account ID (ctidTraderAccountId).\n"
                "6. Set CTRADER_ENABLED=true and restart the server."
            ),
        )
    return CTraderAccountsResponse(
        accounts=[
            {
                "ctidTraderAccountId": acc.get("ctidTraderAccountId"),
                "traderLogin": acc.get("traderLogin"),
                "traderAccountName": acc.get("traderAccountName"),
                "brokerName": acc.get("brokerName"),
                "accountType": acc.get("accountType"),
                "live": acc.get("live"),
            }
            for acc in accounts
        ],
        setup_guide=(
            "Pick one ctidTraderAccountId from the list above and set it as CTRADER_ACCOUNT_ID in .env. "
            "Then generate an Access Token for that account in cTrader app Settings → Open API."
        ) if accounts else None,
    )

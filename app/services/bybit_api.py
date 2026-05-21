"""
Bybit Testnet API Client with HMAC-SHA256 signature authentication.
Only connects to TESTNET — live keys are rejected for safety.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

import requests

TESTNET_BASE = "https://api-testnet.bybit.com"
LIVE_BASE = "https://api.bybit.com"


class BybitAPIError(Exception):
    pass


@dataclass
class BybitCredentials:
    api_key: str
    api_secret: str
    testnet: bool = True


class BybitAPIClient:
    """
    Low-level Bybit V5 API client.
    ONLY allows testnet connections. Live keys are explicitly blocked.
    """

    def __init__(self, creds: BybitCredentials):
        if not creds.testnet:
            raise BybitAPIError(
                "LIVE trading is blocked. Set testnet=True or use SimulationBroker. "
                "Paper trading only works on Bybit Testnet."
            )
        self.creds = creds
        self.base_url = TESTNET_BASE

    def _generate_signature(self, payload: str) -> str:
        timestamp = str(int(time.time() * 1000))
        param_str = timestamp + self.creds.api_key + payload
        signature = hmac.new(
            self.creds.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return timestamp, signature

    def _headers(self, payload: str) -> Dict[str, str]:
        timestamp, signature = self._generate_signature(payload)
        return {
            "X-BAPI-API-KEY": self.creds.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        payload = json.dumps(params) if params else ""
        headers = self._headers(payload)

        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        else:
            resp = requests.post(url, headers=headers, data=payload, timeout=30)

        resp.raise_for_status()
        data = resp.json()

        if data.get("retCode") != 0:
            raise BybitAPIError(f"Bybit API error: {data}")

        return data.get("result", {})

    # ─── ORDER ENDPOINTS ──────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,  # Buy / Sell
        order_type: str = "Market",
        qty: str = "0",
        price: Optional[str] = None,
        stop_loss: Optional[str] = None,
        take_profit: Optional[str] = None,
        category: str = "linear",
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """Place a single order on Bybit Testnet."""
        params: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty,
            "timeInForce": time_in_force,
        }
        if price:
            params["price"] = price
        if stop_loss:
            params["stopLoss"] = stop_loss
        if take_profit:
            params["takeProfit"] = take_profit

        return self._request("POST", "/v5/order/create", params)

    def get_open_orders(
        self,
        symbol: Optional[str] = None,
        category: str = "linear",
    ) -> Dict[str, Any]:
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/v5/order/realtime", params)

    def get_position(
        self,
        symbol: str,
        category: str = "linear",
    ) -> Dict[str, Any]:
        params = {"category": category, "symbol": symbol}
        return self._request("GET", "/v5/position/list", params)

    def cancel_order(
        self,
        symbol: str,
        order_id: str,
        category: str = "linear",
    ) -> Dict[str, Any]:
        params = {
            "category": category,
            "symbol": symbol,
            "orderId": order_id,
        }
        return self._request("POST", "/v5/order/cancel", params)

    def set_trading_stop(
        self,
        symbol: str,
        stop_loss: Optional[str] = None,
        take_profit: Optional[str] = None,
        trailing_stop: Optional[str] = None,
        category: str = "linear",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"category": category, "symbol": symbol}
        if stop_loss:
            params["stopLoss"] = stop_loss
        if take_profit:
            params["takeProfit"] = take_profit
        if trailing_stop:
            params["trailingStop"] = trailing_stop
        return self._request("POST", "/v5/position/trading-stop", params)

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        params = {"accountType": account_type}
        return self._request("GET", "/v5/account/wallet-balance", params)

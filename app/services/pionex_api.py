from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

import requests


SPOT_BALANCES = "/api/v1/account/balances"
SPOT_ORDER = "/api/v1/trade/order"
FUTURES_BALANCES = "/uapi/v1/account/balances"
FUTURES_POSITIONS = "/uapi/v1/account/positions"
FUTURES_ACCOUNT_DETAIL = "/uapi/v1/account/detail"
FUTURES_ORDER = "/uapi/v1/trade/order"
FUTURES_LEVERAGE = "/uapi/v1/account/leverage"
BOT_ORDERS = "/api/v1/bot/orders"
BOT_FUTURES_GRID_ORDER = "/api/v1/bot/orders/futuresGrid/order"


class PionexAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 0,
        result: Optional[dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.result = result or {}
        self.retryable = retryable
        super().__init__(message)


@dataclass(frozen=True)
class PionexCredentials:
    api_key: str
    api_secret: str
    base_url: str = "https://api.pionex.com"
    timeout_seconds: float = 10.0


class PionexClient:
    def __init__(self, credentials: PionexCredentials) -> None:
        self.credentials = credentials
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _signature(self, method: str, path: str, params: dict[str, Any], body: str = "") -> str:
        sorted_query = urlencode(sorted((key, str(value)) for key, value in params.items()))
        sign_source = f"{method.upper()}{path}?{sorted_query}"
        if body:
            sign_source += body
        return hmac.new(
            self.credentials.api_secret.encode("utf-8"),
            sign_source.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        params = dict(params or {})
        body_str = json.dumps(body, separators=(",", ":")) if body else ""
        url = f"{self.credentials.base_url}{path}"

        headers: dict[str, str] = {}
        if auth:
            params["timestamp"] = int(time.time() * 1000)
            headers["PIONEX-KEY"] = self.credentials.api_key
            headers["PIONEX-SIGNATURE"] = self._signature(method, path, params, body_str)

        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=self.credentials.timeout_seconds)
            elif method.upper() == "POST":
                response = self.session.post(
                    url,
                    params=params,
                    data=body_str,
                    headers=headers,
                    timeout=self.credentials.timeout_seconds,
                )
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, headers=headers, timeout=self.credentials.timeout_seconds)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.RequestException as exc:
            raise PionexAPIError(
                message=f"Pionex request failed: {exc}",
                retryable=True,
            ) from exc

        retryable = response.status_code >= 500 or response.status_code == 429
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text}

        if response.status_code != 200 or not payload.get("result", False):
            message = payload.get("message", f"HTTP {response.status_code}")
            raise PionexAPIError(
                message=f"Pionex API error: {message}",
                status_code=response.status_code,
                result=payload,
                retryable=retryable,
            )

        return payload

    def get_spot_balances(self) -> list[dict[str, Any]]:
        response = self._request("GET", SPOT_BALANCES)
        return response.get("data", {}).get("balances", [])

    def get_futures_balances(self) -> list[dict[str, Any]]:
        response = self._request("GET", FUTURES_BALANCES)
        return response.get("data", {}).get("balances", [])

    def get_futures_positions(self, symbol: Optional[str] = None) -> list[dict[str, Any]]:
        params = {"symbol": symbol} if symbol else None
        response = self._request("GET", FUTURES_POSITIONS, params=params)
        return response.get("data", {}).get("positions", [])

    def get_futures_account_detail(self) -> dict[str, Any]:
        response = self._request("GET", FUTURES_ACCOUNT_DETAIL)
        return response.get("data", {})

    def get_bot_orders(
        self,
        status: str = "running",
        base: Optional[str] = None,
        quote: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"status": status}
        if base:
            params["base"] = base.upper()
        if quote:
            params["quote"] = quote.upper()
        response = self._request("GET", BOT_ORDERS, params=params)
        return response.get("data", {})

    def get_futures_grid_order(self, bu_order_id: str) -> dict[str, Any]:
        response = self._request("GET", BOT_FUTURES_GRID_ORDER, params={"buOrderId": bu_order_id})
        return response.get("data", {})

    def get_balance(self, coin: str = "USDT", account: str = "spot") -> float:
        balances = self.get_spot_balances() if account == "spot" else self.get_futures_balances()
        for item in balances:
            if str(item.get("coin", "")).upper() != coin.upper():
                continue
            for key in ("free", "available", "balance"):
                raw = item.get(key)
                if raw is None:
                    continue
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    continue
        return 0.0

    def place_spot_market_buy(self, symbol: str, amount_usdt: float, client_order_id: Optional[str] = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "amount": str(amount_usdt),
        }
        if client_order_id:
            body["clientOrderId"] = client_order_id
        response = self._request("POST", SPOT_ORDER, body=body)
        return response.get("data", {})

    def place_spot_market_sell(self, symbol: str, size: float, client_order_id: Optional[str] = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "size": str(size),
        }
        if client_order_id:
            body["clientOrderId"] = client_order_id
        response = self._request("POST", SPOT_ORDER, body=body)
        return response.get("data", {})

    def place_futures_market_order(
        self,
        symbol: str,
        side: str,
        size: float,
        reduce_only: bool = False,
        position_side: str = "BOTH",
        client_order_id: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET_QTY",
            "size": str(size),
            "reduceOnly": bool(reduce_only),
            "positionSide": position_side,
        }
        if client_order_id:
            body["clientOrderId"] = client_order_id
        response = self._request("POST", FUTURES_ORDER, body=body)
        return response.get("data", {})

    def set_futures_leverage(self, symbol: str, leverage: float) -> dict[str, Any]:
        body = {
            "symbol": symbol,
            "leverage": str(leverage),
        }
        response = self._request("POST", FUTURES_LEVERAGE, body=body)
        return response.get("data", {})

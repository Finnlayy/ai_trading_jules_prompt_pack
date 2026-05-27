from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests


TELEGRAM_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    timeout_seconds: float = 10.0


class TelegramNotifier:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config

    def _is_configured(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.bot_token
            and self.config.chat_id
        )

    def send(self, text: str) -> bool:
        if not self._is_configured():
            return False

        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(
                TELEGRAM_SEND_URL.format(token=self.config.bot_token),
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException:
            return False
        return response.status_code == 200

    def send_execution(
        self,
        symbol: str,
        account_mode: str,
        intent: str,
        side: str,
        size: float,
        price: float,
        trade_id: str,
    ) -> bool:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return self.send(
            "\n".join(
                [
                    "PIONEX DIRECT EXECUTION",
                    f"Trade ID: {trade_id}",
                    f"Symbol: {symbol}",
                    f"Account: {account_mode}",
                    f"Intent: {intent}",
                    f"Side: {side}",
                    f"Size: {size:.8f}",
                    f"Price: {price:.8f}",
                    now,
                ]
            )
        )

    def send_reject(self, symbol: str, reason: str, trade_id: str, intent: Optional[str] = None) -> bool:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        intent_text = intent or "ENTRY"
        return self.send(
            "\n".join(
                [
                    "PIONEX DIRECT REJECT",
                    f"Trade ID: {trade_id}",
                    f"Symbol: {symbol}",
                    f"Intent: {intent_text}",
                    f"Reason: {reason}",
                    now,
                ]
            )
        )

    def send_error(self, context: str, detail: str) -> bool:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return self.send(
            "\n".join(
                [
                    "PIONEX DIRECT ERROR",
                    f"Context: {context}",
                    f"Detail: {detail}",
                    now,
                ]
            )
        )

    def send_heartbeat(self, uptime_minutes: int, trades_today: int, circuit_status: dict) -> bool:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        dd_pct = circuit_status.get("drawdown_pct", 0.0)
        halted = "HALTED" if circuit_status.get("halted") else "OK"
        return self.send(
            "\n".join(
                [
                    "🤖 BOT HEARTBEAT",
                    f"Uptime: {uptime_minutes} min",
                    f"Trades today: {trades_today}",
                    f"Circuit: {halted} (DD: {dd_pct}%)",
                    now,
                ]
            )
        )

    def send_reconcile_alert(self, divergences: list[str]) -> bool:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return self.send(
            "\n".join(
                [
                    "⚠️ LEDGER RECONCILIATION ALERT",
                    "Divergences detected:",
                    *divergences,
                    now,
                ]
            )
        )

    def send_fill_alert(self, symbol: str, order_id: str, fill_price: float, expected_price: float) -> bool:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        slippage = abs(fill_price - expected_price) / expected_price * 100 if expected_price else 0
        return self.send(
            "\n".join(
                [
                    "📋 ORDER FILL ALERT",
                    f"Symbol: {symbol}",
                    f"Order ID: {order_id}",
                    f"Fill price: {fill_price:.4f}",
                    f"Expected: {expected_price:.4f}",
                    f"Slippage: {slippage:.3f}%",
                    now,
                ]
            )
        )

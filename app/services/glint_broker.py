"""GLINT Broker — routes perp trades through Hyperliquid via GLINT.

Current implementation uses Telegram bot interaction for:
  - Position queries
  - Wallet/balance queries  
  - Trade execution (send commands to GLINT bot, read responses)

Future: Direct Hyperliquid API integration when API keys are provided.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import (
    TELEGRAM_NOTIFICATIONS_ENABLED,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    GLINT_ENABLED,
    GLINT_LIVE_TRADING_ENABLED,
    GLINT_TELEGRAM_CHAT_ID,
    GLINT_BOT_USERNAME,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, FinalDecisionEnum, TradeJournalEntry, DirectionEnum
from app.schemas.m8_payload import M8Payload
from app.services.broker_interface import BaseBroker
from app.services.telegram_notifier import TelegramNotifier, TelegramConfig
from app.services.telegram_news_receiver import TelegramNewsReceiver


@dataclass(frozen=True)
class GlintConfig:
    enabled: bool = False
    live_trading_enabled: bool = False
    telegram_chat_id: str = ""
    bot_username: str = ""


class GlintBroker(BaseBroker):
    """Broker for GLINT/Hyperliquid perp trading.

    Uses Telegram bot-to-bot communication in a shared channel:
    1. Our bot sends trade commands to the channel
    2. GLINT bot responds in the same channel
    3. We poll and read GLINT's responses
    """

    def __init__(self, config: Optional[GlintConfig] = None, journal_path: str = "trade_journal.jsonl") -> None:
        self.config = config or GlintConfig(
            enabled=GLINT_ENABLED,
            live_trading_enabled=GLINT_LIVE_TRADING_ENABLED,
            telegram_chat_id=GLINT_TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID,
            bot_username=GLINT_BOT_USERNAME,
        )
        self.journal_path = journal_path
        self.journal: list[TradeJournalEntry] = []

        # Telegram for sending commands to GLINT bot
        self.notifier = TelegramNotifier(
            TelegramConfig(
                enabled=TELEGRAM_NOTIFICATIONS_ENABLED,
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=self.config.telegram_chat_id,
            )
        )

        # Telegram for reading GLINT bot responses
        self.receiver = TelegramNewsReceiver(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=self.config.telegram_chat_id,
            max_messages=100,
        )

        # Pre-seed receiver with any existing messages
        self.receiver.poll_sync(limit=50)

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def is_live_capable(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.live_trading_enabled
            and self.config.telegram_chat_id
        )

    def is_ready(self) -> bool:
        return bool(self.config.enabled and self.config.telegram_chat_id)

    def get_broker_name(self) -> str:
        return "GlintBroker"

    def get_broker_type(self) -> str:
        return "glint"

    def get_broker_mode(self) -> str:
        if self.is_live_capable():
            return "live"
        if self.config.enabled:
            return "dry-run"
        return "simulation"

    def get_positions(self) -> dict[str, Any]:
        """Query GLINT bot for open positions via Telegram."""
        if not self.is_ready():
            return {"error": "not_ready", "positions": []}

        # Send position query and wait for response
        self._send_to_glint("Positions")
        response = self._wait_for_glint_response(timeout_seconds=15)

        return {
            "positions": [],  # Parsed from response in future
            "raw_response": response,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_wallet_balances(self, account_mode: str = "PERPS") -> dict[str, Any]:
        """Query GLINT bot for wallet balance via Telegram."""
        if not self.is_ready():
            return {"error": "not_ready", "balances": []}

        self._send_to_glint("/start")
        response = self._wait_for_glint_response(timeout_seconds=15)

        return {
            "balances": [],
            "raw_response": response,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        """Execute a trade through GLINT/Hyperliquid."""

        if decision != DecisionEnum.PROCEED_TO_SIMULATION:
            self.notifier.send_reject(
                payload.symbol, reject_reason or "REJECTED", f"glint-{payload.signal_id}", payload.intent
            )
            return self._build_entry(
                payload=payload,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reject_reason},
            )

        if not self.config.enabled:
            return self._build_entry(
                payload=payload,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.EXECUTED_SIM,
                simulated_fill={"mode": "GLINT_DISABLED"},
                result={"status": "DRY_RUN_GLINT_DISABLED", "reject_reason": None},
            )

        # Format trade command for GLINT bot
        # Example: "Long BTC for $50" or "Short ETH for $100"
        side = payload.direction.upper()
        size_usdt = self._compute_size(payload)
        symbol = self._normalize_symbol(payload.symbol)

        if payload.intent == "CLOSE":
            command = f"Close {symbol}"
        else:
            command = f"{side} {symbol} for ${size_usdt:.0f}"

        # Send to GLINT bot
        if self.is_live_capable():
            self._send_to_glint(command)
            response = self._wait_for_glint_response(timeout_seconds=30)
            result = {"status": "PENDING_GLINT", "command": command, "response": response}
            final_decision = FinalDecisionEnum.EXECUTED_SIM
            simulated_fill = {}
        else:
            # Dry-run: log what WOULD be sent
            result = {"status": "DRY_RUN", "command": command, "would_execute": True}
            final_decision = FinalDecisionEnum.EXECUTED_SIM
            simulated_fill = {"mode": "GLINT_DRY_RUN", "command": command}

        self.notifier.send(
            f"GLINT {'LIVE' if self.is_live_capable() else 'DRY-RUN'}\n"
            f"Command: {command}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Size: ${size_usdt:.0f}"
        )

        return self._build_entry(
            payload=payload,
            ai_decision=ai_decision,
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_to_glint(self, message: str) -> bool:
        """Send a message to the shared Telegram channel where GLINT bot listens."""
        return self.notifier.send(message)

    def _wait_for_glint_response(self, timeout_seconds: float = 15.0) -> str:
        """Poll Telegram for a response from the GLINT bot.

        This is a blocking wait — use sparingly.
        """
        if not self.config.bot_username:
            return "[No GLINT bot_username configured — cannot filter responses]"

        deadline = time.time() + timeout_seconds
        bot_username_lower = self.config.bot_username.lower().lstrip("@")

        while time.time() < deadline:
            new_msgs = self.receiver.poll_sync(limit=10)
            for msg in reversed(new_msgs):
                sender_lower = msg.sender.lower().lstrip("@")
                if sender_lower == bot_username_lower:
                    return msg.text
            time.sleep(2)

        return f"[Timeout after {timeout_seconds}s — no response from {self.config.bot_username}]"

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for GLINT bot."""
        # GLINT uses: BTC, ETH, etc. (without _USDT_PERP, _USDT or USDT suffix)
        s = symbol.upper()
        for suffix in ["_USDT_PERP", "_USDT", "USDT_PERP", "USDT", ".P", "_PERP", "PERP"]:
            if s.endswith(suffix):
                s = s[:-len(suffix)]
                break
        return s or symbol.upper()

    def _compute_size(self, payload: M8Payload) -> float:
        """Compute trade size in USDT. Placeholder — future: proper sizing."""
        # For now, use fixed small size or payload hint
        size = getattr(payload, "size_usdt", None) or getattr(payload, "size", None)
        if size:
            return float(size)
        # Default $50 for safety
        return 50.0

    def _build_entry(
        self,
        payload: M8Payload,
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: dict[str, Any],
        result: dict[str, Any],
    ) -> TradeJournalEntry:
        """Build a TradeJournalEntry."""
        if payload.direction == "LONG":
            risk = payload.entry_price - payload.stop_price
            reward = payload.target_price - payload.entry_price
        else:
            risk = payload.stop_price - payload.entry_price
            reward = payload.entry_price - payload.target_price
        rr_ratio = reward / risk if risk > 0 else 0.0

        entry = TradeJournalEntry(
            trade_id=f"glint-{payload.signal_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            risk_reward=rr_ratio,
            m8_score=payload.confluence_score,
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )
        self.journal.append(entry)
        return entry

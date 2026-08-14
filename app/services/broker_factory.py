"""Broker factory for clean single/multi-mode broker selection.

Supported modes (single):
  - simulation     → SimulationBroker
  - paper          → PaperBroker
  - pionex_relay   → PionexRelayBroker
  - pionex_direct  → PionexDirectBroker
  - glint          → GlintBroker

Multi-mode (future):
  - multi          → MultiBroker (orchestrates multiple brokers simultaneously)
"""
from __future__ import annotations

from typing import Optional

from app.core.config import BROKER_MODE
from app.services.broker_interface import BaseBroker
from app.services.broker import SimulationBroker
from app.services.paper_broker import PaperBroker
from app.services.pionex_relay_broker import PionexRelayBroker
from app.services.pionex_direct_broker import PionexDirectBroker
from app.services.glint_broker import GlintBroker


class BrokerFactory:
    """Creates broker instances based on configuration."""

    _VALID_SINGLE_MODES = {
        "simulation",
        "orderbook_sim",
        "paper",
        "pionex_relay",
        "relay",
        "pionex",
        "pionex_direct",
        "direct",
        "pionex_api",
        "glint",
        "ctrader",
        "ctrader_direct",
        "ctrader_fix",
        "kraken",
        "kraken_paper",
        "krakenpaper",
    }

    @classmethod
    def create(cls, mode: Optional[str] = None, journal_path: str = "trade_journal.jsonl") -> BaseBroker:
        """Create a broker instance for the given mode.

        Args:
            mode: Broker mode string. Defaults to BROKER_MODE env var.
            journal_path: Path for trade journal logging.
        """
        mode = (mode or BROKER_MODE).strip().lower()

        if mode in {"simulation",
        "orderbook_sim", "sim"}:
            return SimulationBroker()

        if mode == "orderbook_sim":
            # For MVP, we can reuse SimulationBroker logic but ideally we'd inject the OrderbookSimulator
            return SimulationBroker()

        if mode == "paper":
            return PaperBroker()

        if mode in {"pionex_relay", "relay", "pionex"}:
            return PionexRelayBroker()

        if mode in {"pionex_direct", "direct", "pionex_api"}:
            return PionexDirectBroker(journal_path=journal_path)

        if mode == "glint":
            return GlintBroker(journal_path=journal_path)

        if mode in {"ctrader", "ctrader_direct"}:
            from app.services.ctrader_broker import CTraderBroker
            return CTraderBroker(journal_path=journal_path)

        if mode == "ctrader_fix":
            from app.services.ctrader_fix_broker import CTraderFixBroker, CTraderFixConfig
            from app.core.config import (
                CTRADER_FIX_ENABLED,
                CTRADER_FIX_HOST,
                CTRADER_FIX_LIVE_TRADING_ENABLED,
                CTRADER_FIX_PORT,
                CTRADER_FIX_SENDER_COMP_ID,
                CTRADER_FIX_TARGET_COMP_ID,
                CTRADER_FIX_PASSWORD,
                CTRADER_FIX_SENDER_SUB_ID,
            )
            config = CTraderFixConfig()
            return CTraderFixBroker(config=config, journal_path=journal_path)

        if mode == "kraken":
            from app.services.kraken_broker import KrakenBroker, KrakenConfig
            return KrakenBroker(config=KrakenConfig(), journal_path=journal_path)

        if mode in {"kraken_paper", "krakenpaper"}:
            from app.services.kraken_paper_broker import KrakenPaperBroker, KrakenPaperConfig
            return KrakenPaperBroker(config=KrakenPaperConfig())

        # Fallback
        return SimulationBroker()

    @classmethod
    def is_valid_mode(cls, mode: str) -> bool:
        return mode.strip().lower() in cls._VALID_SINGLE_MODES

    @classmethod
    def available_modes(cls) -> list[str]:
        return sorted(cls._VALID_SINGLE_MODES)

    @classmethod
    def mode_display_name(cls, mode: str) -> str:
        mapping = {
            "simulation": "Simulation",
            "orderbook_sim": "Orderbook Simulator",
            "paper": "Paper Trading",
            "pionex_relay": "Pionex Relay",
            "relay": "Pionex Relay",
            "pionex": "Pionex Relay",
            "pionex_direct": "Pionex Direct",
            "direct": "Pionex Direct",
            "pionex_api": "Pionex Direct",
            "glint": "GLINT (Hyperliquid)",
            "ctrader": "cTrader Direct",
            "ctrader_direct": "cTrader Direct",
            "ctrader_fix": "cTrader FIX",
            "kraken": "Kraken",
            "kraken_paper": "Kraken Paper",
            "krakenpaper": "Kraken Paper",
        }
        return mapping.get(mode.strip().lower(), mode)

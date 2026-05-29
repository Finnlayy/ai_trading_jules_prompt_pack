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
    }

    @classmethod
    def create(cls, mode: Optional[str] = None, journal_path: str = "trade_journal.jsonl") -> BaseBroker:
        """Create a broker instance for the given mode.

        Args:
            mode: Broker mode string. Defaults to BROKER_MODE env var.
            journal_path: Path for trade journal logging.
        """
        mode = (mode or BROKER_MODE).strip().lower()

        if mode in {"simulation", "sim"}:
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
            config = CTraderFixConfig(
                enabled=True,
                host="demo-uk-eqx-01.p.c-trader.com",
                port=5212,
                sender_comp_id="",
                password="",
            )
            return CTraderFixBroker(config=config, journal_path=journal_path)

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
        }
        return mapping.get(mode.strip().lower(), mode)

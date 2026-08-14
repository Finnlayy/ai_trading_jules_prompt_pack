from app.services.pionex_position_ledger import LedgerEntry
import pytest
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig
from app.schemas.journal import DecisionEnum, FinalDecisionEnum


def _payload(signal_id: str, symbol: str = "BTCUSDT", direction: str = "LONG", intent: str = "ENTRY", account_mode: str = "SPOT"):
    from app.schemas.m8_payload import M8Payload
    return M8Payload(
        signal_id=signal_id,
        symbol=symbol,
        timeframe="1m",
        direction=direction,
        intent=intent,
        account_mode=account_mode,
        timestamp="2026-05-20T10:00:00Z",
        entry_price=100.0,
        stop_price=90.0,
        target_price=120.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0,
    )


def test_reconcile_ledger_detects_divergence():
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("BTC_USDT_PERP",),
        ),
        journal_path="/tmp/test_reconcile_clean.jsonl",
    )

    class FakeClient:
        def get_futures_positions(self):
            return [{"symbol": "BTC_USDT_PERP", "size": "0.5"}]

    broker.client = FakeClient()
    broker.ledger.apply_entry(LedgerEntry(
        symbol="BTC_USDT_PERP",
        account_mode="FUTURES",
        direction="LONG",
        size_base=1.0,
        entry_price=100.0,
        risk_amount=10.0,
    ))

    result = broker.reconcile_ledger()
    assert result["checked"] is True
    assert result["divergence_count"] == 1
    assert "local=1.000000 vs exchange=0.500000" in result["divergences"][0]


def test_reconcile_ledger_no_client():
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            api_key="",
            api_secret="",
        ),
    )
    result = broker.reconcile_ledger()
    assert result["checked"] is False

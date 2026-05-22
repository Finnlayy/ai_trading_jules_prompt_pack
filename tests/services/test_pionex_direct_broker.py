import pytest
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig
from app.schemas.m8_payload import M8Payload
from app.schemas.journal import DecisionEnum, FinalDecisionEnum

def create_payload(symbol="BTCUSD") -> M8Payload:
    return M8Payload(
        signal_id="test-sig-1",
        symbol=symbol,
        timeframe="1h",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0
    )

def test_dry_run_direct():
    config = PionexDirectConfig(
        enabled=True,
        live_trading_enabled=False,
        api_key="mock",
        api_secret="mock",
        allowed_symbols=["BTC_USDT"]
    )
    broker = PionexDirectBroker(config)
    payload = create_payload()

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_DIRECT"
    assert entry.result["mapped_symbol"] == "BTC_USDT"

def test_live_trading_direct():
    config = PionexDirectConfig(
        enabled=True,
        live_trading_enabled=True,
        api_key="mock",
        api_secret="mock",
        allowed_symbols=["BTC_USDT"]
    )
    broker = PionexDirectBroker(config)
    payload = create_payload()

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "SENT_TO_PIONEX_DIRECT"

def test_allowlist_rejection():
    config = PionexDirectConfig(
        enabled=True,
        live_trading_enabled=False,
        api_key="mock",
        api_secret="mock",
        allowed_symbols=["BTC_USDT"]
    )
    broker = PionexDirectBroker(config)
    payload = create_payload(symbol="XAGUSDT.P")

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.REJECTED
    assert "SYMBOL_NOT_IN_ALLOWLIST" in entry.result["reject_reason"]

def test_allowlist_acceptance_xag():
    config = PionexDirectConfig(
        enabled=True,
        live_trading_enabled=False,
        api_key="mock",
        api_secret="mock",
        allowed_symbols=["BTC_USDT", "XAG_USDT_PERP"]
    )
    broker = PionexDirectBroker(config)
    payload = create_payload(symbol="XAGUSDT.P")

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_DIRECT"
    assert entry.result["mapped_symbol"] == "XAG_USDT_PERP"

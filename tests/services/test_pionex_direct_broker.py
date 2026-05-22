from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig


def _payload(
    signal_id: str,
    direction: str = "LONG",
    intent: str = "ENTRY",
    account_mode: str = "SPOT",
    entry_price: float = 100.0,
) -> M8Payload:
    return M8Payload(
        signal_id=signal_id,
        symbol="BTCUSDT",
        timeframe="1m",
        direction=direction,
        intent=intent,
        account_mode=account_mode,
        timestamp="2026-05-20T10:00:00Z",
        entry_price=entry_price,
        stop_price=99.0 if direction == "LONG" else 101.0,
        target_price=102.0 if direction == "LONG" else 98.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=2.0,
    )


def test_pionex_direct_broker_dry_run_entry(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    entry = broker.execute_trade(
        payload=_payload("direct-1"),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_DIRECT"
    assert entry.result["ledger_delta"]["action"] == "ENTRY"


def test_pionex_direct_broker_rejects_symbol_not_allowed(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("ETH_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    entry = broker.execute_trade(
        payload=_payload("direct-2"),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert entry.final_decision == FinalDecisionEnum.REJECTED
    assert "SYMBOL_NOT_ALLOWED" in entry.result["reject_reason"]


def test_pionex_direct_broker_entry_then_close_uses_ledger(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    entry = broker.execute_trade(
        payload=_payload("direct-3-entry", direction="LONG", intent="ENTRY", entry_price=100.0),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )
    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM

    close = broker.execute_trade(
        payload=_payload("direct-3-close", direction="LONG", intent="CLOSE", entry_price=101.0),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )
    assert close.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert close.result["status"] == "CLOSED_DRY_RUN"
    assert close.result["realized_pnl_quote"] > 0
    assert close.result["ledger_delta"]["action"] == "CLOSE"


def test_pionex_direct_broker_live_spot_entry_calls_client(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=True,
            api_key="k",
            api_secret="s",
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    class FakeClient:
        def __init__(self):
            self.buy_called = False

        def get_balance(self, coin="USDT", account="spot"):
            return 500.0

        def place_spot_market_buy(self, symbol: str, amount_usdt: float):
            self.buy_called = True
            return {"orderId": "spot-live-1", "symbol": symbol, "amount": amount_usdt}

    fake = FakeClient()
    broker.client = fake

    entry = broker.execute_trade(
        payload=_payload("direct-live-1", direction="LONG", account_mode="SPOT"),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "SENT_TO_PIONEX_DIRECT"
    assert fake.buy_called is True


def test_pionex_direct_broker_futures_mode3_applies_payload_leverage(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=True,
            api_key="k",
            api_secret="s",
            allowed_symbols=("BTC_USDT_PERP",),
            futures_mode="mode3",
            allow_payload_leverage=True,
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    class FakeClient:
        def __init__(self):
            self.leverage_calls = 0
            self.order_calls = 0

        def get_balance(self, coin="USDT", account="futures"):
            return 500.0

        def set_futures_leverage(self, symbol: str, leverage: float):
            self.leverage_calls += 1
            return {"symbol": symbol, "leverage": leverage}

        def place_futures_market_order(self, **kwargs):
            self.order_calls += 1
            return {"orderId": "fut-live-1", **kwargs}

    fake = FakeClient()
    broker.client = fake

    payload = _payload(
        "direct-live-2",
        direction="SHORT",
        account_mode="FUTURES",
    )
    payload.leverage = 4
    entry = broker.execute_trade(payload=payload, decision=DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "SENT_TO_PIONEX_DIRECT"
    assert fake.leverage_calls == 1
    assert fake.order_calls == 1

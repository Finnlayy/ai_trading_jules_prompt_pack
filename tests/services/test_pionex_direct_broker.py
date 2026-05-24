from app.schemas.journal import DecisionEnum, FinalDecisionEnum
import pytest
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig
from app.schemas.m8_payload import M8Payload

def create_payload(symbol="BTC_USDT") -> M8Payload:
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
        allowed_symbols=("BTC_USDT",)
    )
    broker = PionexDirectBroker(config)
    payload = create_payload()

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_DIRECT"
    assert entry.result["ledger_delta"]["symbol"] == "BTC_USDT"

def test_live_trading_direct():
    config = PionexDirectConfig(
        enabled=True,
        live_trading_enabled=True,
        api_key="mock",
        api_secret="mock",
        allowed_symbols=("BTC_USDT",)
    )
    broker = PionexDirectBroker(config)
    class FakeClient:
        def place_spot_market_buy(self, **kwargs):
            return {"orderId": "123"}
        def get_balance(self, **kwargs):
            return 1000.0
    broker.client = FakeClient()
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
        allowed_symbols=("BTC_USDT",)
    )
    broker = PionexDirectBroker(config)
    payload = create_payload(symbol="XAGUSDT.P")

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.REJECTED
    assert "SYMBOL_NOT_ALLOWED" in entry.result["reject_reason"]

def test_allowlist_acceptance_xag():
    config = PionexDirectConfig(
        enabled=True,
        live_trading_enabled=False,
        api_key="mock",
        api_secret="mock",
        allowed_symbols=("BTC_USDT", "XAG_USDT_PERP")
    )
    broker = PionexDirectBroker(config)
    payload = create_payload(symbol="XAGUSDT.P")

    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_DIRECT"
    assert entry.result["ledger_delta"]["symbol"] == "XAG_USDT_PERP"
from app.schemas.m8_payload import M8Payload
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig


def _payload(
    signal_id: str,
    symbol: str = "BTCUSDT",
    direction: str = "LONG",
    intent: str = "ENTRY",
    account_mode: str = "SPOT",
    entry_price: float = 100.0,
) -> M8Payload:
    return M8Payload(
        signal_id=signal_id,
        symbol=symbol,
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


def test_pionex_direct_broker_accepts_tradingview_perp_suffix(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("XAG_USDT_PERP",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    entry = broker.execute_trade(
        payload=_payload("direct-xag-1", symbol="xagusdt.p"),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_DIRECT"
    assert entry.result["ledger_delta"]["symbol"] == "XAG_USDT_PERP"
    assert entry.result["ledger_delta"]["account_mode"] == "FUTURES"
    assert entry.simulated_fill["account_mode"] == "FUTURES"


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

        def place_spot_market_buy(self, symbol: str, amount_usdt: float, client_order_id: str = None):
            self.buy_called = True
            self.captured_client_order_id = client_order_id
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
            self.captured_kwargs = kwargs
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


def test_pionex_direct_broker_returns_full_wallet_assets(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            api_key="k",
            api_secret="s",
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    class FakeClient:
        def get_spot_balances(self):
            return [
                {"coin": "USDT", "available": "8.4", "locked": "0"},
                {"coin": "ETH", "available": "0.2", "locked": "0.01", "usdValue": "700"},
            ]

        def get_futures_balances(self):
            return [
                {"coin": "USDT", "available": "19.00", "frozen": "0.38"},
                {"coin": "BTC", "available": "0.01", "usdValue": "650"},
            ]

    broker.client = FakeClient()

    primary = broker.get_wallet_balances(account_mode="SPOT")
    futures = broker.get_wallet_balances(account_mode="FUTURES")

    assert primary["balance"] == 8.4
    assert primary["assets"][1]["coin"] == "ETH"
    assert primary["assets"][1]["value_usdt"] == 700.0
    assert futures["balance"] == 19.38
    assert futures["assets"][0]["available"] == 19.0
    assert futures["assets"][0]["locked"] == 0.38
    assert futures["assets"][0]["value_usdt"] == 19.38
    assert futures["assets"][1]["coin"] == "BTC"


def test_pionex_direct_broker_returns_open_futures_positions(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            api_key="k",
            api_secret="s",
            allowed_symbols=("ZEC_USDT_PERP",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    class FakeClient:
        def get_futures_positions(self):
            return [
                {
                    "positionId": "pos-1",
                    "symbol": "ZEC_USDT_PERP",
                    "positionSide": "LONG",
                    "netSize": "0.4",
                    "avgPrice": "42",
                    "markPrice": "43",
                    "initialMargin": "8.25",
                    "maintMargin": "0.33",
                    "unrealizedPnL": "0.4",
                    "leverage": "5",
                    "liquidationPrice": "30",
                    "isolatedMode": "ISOLATED",
                    "riskState": "NORMAL",
                }
            ]

    broker.client = FakeClient()

    positions = broker.get_open_positions()

    assert positions["open_count"] == 1
    assert positions["positions"][0]["symbol"] == "ZEC_USDT_PERP"
    assert positions["positions"][0]["is_zcash"] is True
    assert positions["summary"]["total_initial_margin"] == 8.25
    assert positions["summary"]["zcash_initial_margin"] == 8.25
    assert positions["summary"]["total_unrealized_pnl"] == 0.4


def test_pionex_direct_broker_returns_running_bot_margin(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            api_key="k",
            api_secret="s",
            allowed_symbols=("ZEC_USDT_PERP",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    class FakeClient:
        def get_bot_orders(self, status="running"):
            return {
                "results": [
                    {
                        "buOrderId": "bot-1",
                        "buOrderType": "futures_grid",
                        "base": "ZEC",
                        "quote": "USDT",
                    }
                ]
            }

        def get_futures_grid_order(self, bu_order_id):
            return {
                "buOrderId": bu_order_id,
                "buOrderType": "futures_grid",
                "base": "ZEC",
                "quote": "USDT",
                "status": "running",
                "botName": "Zcash grid",
                "buOrderData": {
                    "marginBalance": "9.5",
                    "quoteInvestment": "10",
                    "extraBalance": "0.5",
                    "position": "0.2",
                    "leverage": "3",
                    "liquidationPrice": "20",
                    "riskStatus": "TRADING",
                },
            }

    broker.client = FakeClient()

    bots = broker.get_running_bots()

    assert bots["open_count"] == 1
    assert bots["bots"][0]["symbol"] == "ZEC_USDT"
    assert bots["bots"][0]["is_zcash"] is True
    assert bots["summary"]["zcash_bot_count"] == 1
    assert bots["summary"]["zcash_margin_balance"] == 9.5
    assert bots["summary"]["total_quote_investment"] == 10.0

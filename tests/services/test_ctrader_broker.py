from datetime import datetime, timezone

from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.broker_factory import BrokerFactory
from app.services.ctrader_broker import CTraderBroker, CTraderConfig, CTRADER_LIVE_HOST


class FakeBridge:
    def __init__(self):
        self.connected = False
        self.authenticated = False
        self.market_orders = []
        self.close_orders = []
        self.symbols = {"EURUSD": 1, "GBPUSD": 2}
        self.positions = []
        self.trader = {"balance": 100000, "money_digits": 2, "brokerName": "fake"}

    def status(self):
        return {
            "connected": self.connected,
            "app_authenticated": self.authenticated,
            "account_authenticated": self.authenticated,
            "host": "live.ctraderapi.com" if self.authenticated else "demo.ctraderapi.com",
            "port": 5035,
            "last_error": None,
            "last_connected_at": datetime.now(timezone.utc).isoformat() if self.connected else None,
        }

    def is_authenticated(self):
        return self.authenticated

    def connect(self):
        self.connected = True
        self.authenticated = True
        return self.status()

    def disconnect(self):
        self.connected = False
        self.authenticated = False
        return self.status()

    def refresh_symbols(self):
        return self.symbols

    def send_market_order(self, order):
        self.market_orders.append(order)
        return {"orderId": "order-1", "clientOrderId": order["client_order_id"]}

    def close_position(self, position_id, volume):
        self.close_orders.append({"position_id": position_id, "volume": volume})
        return {"positionId": position_id, "volume": volume}

    def reconcile(self):
        return {"positions": self.positions, "orders": []}

    def get_trader(self):
        return self.trader


def _config(tmp_path, enabled=True, live=False):
    return CTraderConfig(
        enabled=enabled,
        live_trading_enabled=live,
        client_id="client",
        client_secret="secret",
        access_token="token",
        account_id=12345,
        host="demo.ctraderapi.com",
        symbol_map_path=str(tmp_path / "ctrader_symbols.json"),
    )


def _payload(signal_id="sig-1", direction="LONG", intent="ENTRY", quantity=0.02):
    return M8Payload(
        signal_id=signal_id,
        symbol="EURUSD",
        timeframe="1m",
        direction=direction,
        intent=intent,
        account_mode="FUTURES",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=1.1000,
        stop_price=1.0950 if direction == "LONG" else 1.1050,
        target_price=1.1100 if direction == "LONG" else 1.0900,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=1.0,
        execution_quantity=quantity,
    )


def test_ctrader_is_not_ready_when_disabled(tmp_path):
    broker = CTraderBroker(config=_config(tmp_path, enabled=False), bridge=FakeBridge())

    assert broker.is_ready() is False
    assert broker.is_live_capable() is False
    assert broker.get_broker_mode() == "simulation"


def test_live_capable_false_when_live_flag_disabled(tmp_path):
    bridge = FakeBridge()
    bridge.connect()
    broker = CTraderBroker(config=_config(tmp_path, enabled=True, live=False), bridge=bridge)

    assert broker.is_ready() is True
    assert broker.is_live_capable() is False
    assert broker.get_broker_mode() == "dry-run"


def test_live_flag_forces_live_host(tmp_path):
    config = _config(tmp_path, enabled=True, live=True)

    assert config.effective_host == CTRADER_LIVE_HOST


def test_live_capable_requires_authenticated_bridge(tmp_path):
    bridge = FakeBridge()
    broker = CTraderBroker(config=_config(tmp_path, enabled=True, live=True), bridge=bridge)

    assert broker.is_live_capable() is False
    bridge.connect()
    assert broker.is_live_capable() is True


def test_broker_name_type_and_health(tmp_path):
    broker = CTraderBroker(config=_config(tmp_path), bridge=FakeBridge())

    assert broker.get_broker_name() == "CTrader"
    assert broker.get_broker_type() == "ctrader"
    health = broker.health()
    assert health["connection"]["connected"] is False
    assert health["symbols_cached"] == 0


def test_symbol_map_json_created_on_refresh(tmp_path):
    bridge = FakeBridge()
    broker = CTraderBroker(config=_config(tmp_path), bridge=bridge)

    symbols = broker.refresh_symbols()

    assert symbols["EURUSD"] == 1
    assert (tmp_path / "ctrader_symbols.json").exists()


def test_symbol_map_loaded_from_json(tmp_path):
    symbol_file = tmp_path / "ctrader_symbols.json"
    symbol_file.write_text('{"EURUSD":1}', encoding="utf-8")

    broker = CTraderBroker(config=_config(tmp_path), bridge=FakeBridge())

    assert broker.get_symbols()["EURUSD"] == 1


def test_lots_convert_to_ctrader_protocol_volume(tmp_path):
    broker = CTraderBroker(config=_config(tmp_path), bridge=FakeBridge())

    assert broker._lots_to_protocol_volume(0.02) == 200000


def test_dry_run_execute_builds_order_without_sending(tmp_path):
    bridge = FakeBridge()
    broker = CTraderBroker(config=_config(tmp_path, enabled=True, live=False), bridge=bridge)
    broker.symbol_map = {"EURUSD": 1}

    entry = broker.execute_trade(_payload(), DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_CTRADER"
    assert entry.result["order"]["trade_side"] == "BUY"
    assert entry.result["order"]["volume"] == 200000
    assert bridge.market_orders == []


def test_live_execute_sends_market_order(tmp_path):
    bridge = FakeBridge()
    bridge.connect()
    broker = CTraderBroker(config=_config(tmp_path, enabled=True, live=True), bridge=bridge)
    broker.symbol_map = {"EURUSD": 1}

    entry = broker.execute_trade(_payload(), DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.result["status"] == "SENT_TO_CTRADER"
    assert bridge.market_orders[0]["client_order_id"] == "metricflow-sig-1"


def test_unknown_live_symbol_rejected_after_refresh(tmp_path):
    bridge = FakeBridge()
    bridge.symbols = {"GBPUSD": 2}
    broker = CTraderBroker(config=_config(tmp_path, enabled=True, live=True), bridge=bridge)

    entry = broker.execute_trade(_payload(), DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.REJECTED
    assert "CTRADER_SYMBOL_NOT_FOUND" in entry.result["reject_reason"]


def test_close_intent_dry_runs_close_request(tmp_path):
    bridge = FakeBridge()
    bridge.positions = [
        {
            "position_id": 77,
            "symbol": "EURUSD",
            "direction": "LONG",
            "entry_price": 1.1,
            "current_price": 1.101,
            "size": 2000,
            "volume": 200000,
            "open_time": datetime.now(timezone.utc),
            "stop_price": 1.095,
            "target_price": 1.11,
        }
    ]
    broker = CTraderBroker(config=_config(tmp_path, enabled=True, live=False), bridge=bridge)

    entry = broker.execute_trade(_payload("close-1", intent="CLOSE"), DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.result["status"] == "DRY_RUN_CTRADER_CLOSE"
    assert entry.result["close"]["position_id"] == 77
    assert bridge.close_orders == []


def test_get_positions_normalizes_bridge_snapshot(tmp_path):
    bridge = FakeBridge()
    bridge.positions = [
        {
            "position_id": 77,
            "symbol": "EURUSD",
            "direction": "LONG",
            "entry_price": 1.1,
            "current_price": 1.101,
            "size": 2000,
            "volume": 200000,
            "open_time": datetime.now(timezone.utc),
            "stop_price": 1.095,
            "target_price": 1.11,
        }
    ]
    broker = CTraderBroker(config=_config(tmp_path), bridge=bridge)

    result = broker.get_positions()

    assert result["status"] == "ok"
    assert result["positions"][0]["symbol"] == "EURUSD"
    assert result["positions"][0]["direction"] == "LONG"


def test_get_wallet_balances_normalizes_money_digits(tmp_path):
    broker = CTraderBroker(config=_config(tmp_path), bridge=FakeBridge())

    result = broker.get_wallet_balances()

    assert result["status"] == "ok"
    assert result["balance"] == 1000.0
    assert result["free_margin"] == 1000.0


def test_broker_factory_registers_ctrader_mode(tmp_path):
    broker = BrokerFactory.create("ctrader", journal_path=str(tmp_path / "journal.jsonl"))

    assert broker.get_broker_type() == "ctrader"
    assert BrokerFactory.is_valid_mode("ctrader_direct") is True
    assert BrokerFactory.mode_display_name("ctrader") == "cTrader Direct"

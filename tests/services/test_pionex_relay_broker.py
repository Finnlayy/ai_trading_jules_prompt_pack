from unittest.mock import Mock, patch

from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.pionex_relay_broker import PionexRelayBroker, PionexRelayConfig


def create_valid_payload(direction: str = "LONG") -> M8Payload:
    return M8Payload(
        signal_id="sig-001",
        symbol="HYPEUSDT",
        timeframe="1m",
        direction=direction,
        timestamp="2026-05-20T10:00:00Z",
        entry_price=50.0,
        stop_price=49.0 if direction == "LONG" else 51.0,
        target_price=52.0 if direction == "LONG" else 48.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0,
    )


def test_pionex_relay_broker_dry_run_does_not_post():
    broker = PionexRelayBroker(
        PionexRelayConfig(
            relay_url="http://127.0.0.1:5000/webhook",
            signal_bot_uuid="uuid-123",
            contracts="1",
            enabled=False,
        )
    )

    with patch("app.services.pionex_relay_broker.requests.post") as post:
        entry = broker.execute_trade(create_valid_payload(), DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "DRY_RUN_RELAY"
    assert entry.result["relay_payload"]["data"]["action"] == "buy"
    post.assert_not_called()


def test_pionex_relay_broker_posts_when_enabled():
    broker = PionexRelayBroker(
        PionexRelayConfig(
            relay_url="http://127.0.0.1:5000/webhook",
            signal_bot_uuid="uuid-123",
            contracts="0.5",
            enabled=True,
        )
    )
    response = Mock(status_code=200)
    response.json.return_value = {"ok": True}

    with patch("app.services.pionex_relay_broker.requests.post", return_value=response) as post:
        entry = broker.execute_trade(create_valid_payload("SHORT"), DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "SENT_TO_PIONEX_RELAY"
    sent_payload = post.call_args.kwargs["json"]
    assert sent_payload["data"]["action"] == "sell"
    assert sent_payload["data"]["contracts"] == "0.5"
    assert sent_payload["data"]["position_size"] == "-0.5"
    assert sent_payload["signal_type"] == "uuid-123"


def test_pionex_relay_broker_rejects_without_sending_on_risk_reject():
    broker = PionexRelayBroker(
        PionexRelayConfig(
            relay_url="http://127.0.0.1:5000/webhook",
            signal_bot_uuid="uuid-123",
            enabled=True,
        )
    )

    with patch("app.services.pionex_relay_broker.requests.post") as post:
        entry = broker.execute_trade(create_valid_payload(), DecisionEnum.REJECT, reject_reason="LOW_RR")

    assert entry.final_decision == FinalDecisionEnum.REJECTED
    assert entry.result["status"] == "REJECTED"
    assert entry.result["reject_reason"] == "LOW_RR"
    post.assert_not_called()

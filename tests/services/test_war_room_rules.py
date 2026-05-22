from app.schemas.ai_review import DecisionEnum as AIDecisionEnum, SignalReview
from app.schemas.journal import DecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig
from app.services.pionex_kelly_sizer import KellyConfig, KellySizer
from app.services.risk_engine import RiskEngine
from app.services.war_room_rules import WarRoomColor, WarRoomCommand, ai_rule_violation, classify_order


def _payload(**overrides) -> M8Payload:
    data = {
        "signal_id": "war-room-1",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 100.0,
        "stop_price": 99.0,
        "target_price": 102.0,
        "confluence_score": 88.0,
        "relative_volume": 1.7,
        "crisis_score": 10.0,
        "mc_dispersion": 1.5,
        "spread": 1.0,
    }
    data.update(overrides)
    return M8Payload(**data)


def _ai_review(**overrides) -> SignalReview:
    data = {
        "schema_version": "1.0",
        "signal_id": "war-room-ai",
        "decision": AIDecisionEnum.PROCEED_TO_SIMULATION,
        "confidence": 0.9,
        "reason_codes": [],
        "risk_flags": [],
        "reject_reason": None,
        "requires_human_review": False,
    }
    data.update(overrides)
    return SignalReview(**data)


def test_war_room_classifies_vip_conditions_as_green_go():
    decision = classify_order(_payload())

    assert decision.color == WarRoomColor.GREEN
    assert decision.command == WarRoomCommand.GO
    assert "VIP_REGIME_CANDIDATE" in decision.reason_codes


def test_war_room_chop_index_forces_standby():
    result = RiskEngine().evaluate(_payload(chop_index=70.0), _ai_review())

    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "CHOP_STANDBY"


def test_war_room_unconfirmed_bar_blocks_entry():
    result = RiskEngine().evaluate(_payload(bar_confirmed=False), _ai_review())

    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "BAR_NOT_CONFIRMED"


def test_war_room_hard_kill_blocks_new_entries():
    result = RiskEngine().evaluate(_payload(drawdown_pct=25.0), _ai_review())

    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "DRAWDOWN_HARD_KILL"


def test_close_intent_bypasses_entry_war_room_gates():
    result = RiskEngine().evaluate(
        _payload(intent="CLOSE", order_command="KILL", drawdown_pct=30.0),
        _ai_review(),
    )

    assert result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION
    assert result["reject_reason"] is None


def test_ai_scope_violation_rejects_entry():
    result = RiskEngine().evaluate(
        _payload(),
        _ai_review(reason_codes=["FORCE_LIVE_ORDER"]),
    )

    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "AI_SCOPE_VIOLATION"


def test_ai_low_confidence_rejects_entry():
    assert ai_rule_violation(_ai_review(confidence=0.2)) == "AI_LOW_CONFIDENCE"


def test_direct_broker_records_orange_risk_cap(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )
    broker.sizer = KellySizer(
        KellyConfig(
            deploy_mode="fixed",
            fixed_risk_pct=2.0,
            min_risk_pct=0.2,
            max_risk_pct=2.0,
            min_order_usdt=5.0,
            max_order_usdt=10_000.0,
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    entry = broker.execute_trade(
        payload=_payload(macro_event_risk=True),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert entry.final_decision == "EXECUTED_SIM"
    assert entry.simulated_fill["war_room"]["color"] == "ORANGE"
    assert entry.simulated_fill["war_room"]["risk_cap_pct"] == 1.0
    assert entry.simulated_fill["risk_pct"] == 1.0


def test_direct_broker_rejects_hold_command_without_risk_engine(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    entry = broker.execute_trade(
        payload=_payload(order_command="HOLD"),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert entry.final_decision == "REJECTED"
    assert entry.result["reject_reason"] == "WAR_ROOM_HOLD_COMMAND"

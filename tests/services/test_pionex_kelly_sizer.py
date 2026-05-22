import json

from app.schemas.m8_payload import M8Payload
from app.services.pionex_kelly_sizer import KellyConfig, KellySizer


def _payload() -> M8Payload:
    return M8Payload(
        signal_id="kelly-1",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        confluence_score=80.0,
        crisis_score=10.0,
        mc_dispersion=1.0,
        spread=1.0,
    )


def _write_journal(path, returns):
    with open(path, "w", encoding="utf-8") as handle:
        for idx, ret in enumerate(returns):
            entry = {
                "trade_id": f"t-{idx}",
                "final_decision": "EXECUTED_SIM",
                "result": {
                    "status": "CLOSED",
                    "realized_pnl_quote": float(ret),
                    "risk_amount": 10.0,
                },
            }
            handle.write(json.dumps(entry) + "\n")


def test_kelly_sizer_uses_floor_when_not_enough_history(tmp_path):
    journal = tmp_path / "journal.jsonl"
    _write_journal(journal, [1.0, -1.0, 2.0])

    sizer = KellySizer(
        KellyConfig(
            deploy_mode="half",
            min_trades=10,
            min_risk_pct=0.3,
            max_risk_pct=2.0,
        ),
        journal_path=str(journal),
    )
    result = sizer.size_trade(_payload(), balance=1000.0)

    assert result.history_trades == 3
    assert result.risk_pct == 0.3
    assert result.size_base > 0


def test_kelly_sizer_computes_half_kelly_and_clamps(tmp_path):
    journal = tmp_path / "journal.jsonl"
    # pnl relative to risk amount (10): +0.5R / -0.2R pattern
    _write_journal(journal, [5, 5, 5, -2, 5, -2, 5, 5, -2, 5])

    sizer = KellySizer(
        KellyConfig(
            deploy_mode="half",
            min_trades=5,
            min_risk_pct=0.2,
            max_risk_pct=1.5,
            max_order_usdt=200.0,
        ),
        journal_path=str(journal),
    )
    result = sizer.size_trade(_payload(), balance=2000.0)

    assert result.history_trades == 10
    assert result.kelly_fraction >= 0.0
    assert 0.2 <= result.risk_pct <= 1.5
    assert result.order_value_usdt <= 200.0

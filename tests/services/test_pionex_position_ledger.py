import json

from app.services.pionex_position_ledger import PositionLedger


def test_position_ledger_entry_and_close_flow():
    ledger = PositionLedger()
    state = ledger.apply_entry(
        symbol="BTC_USDT",
        account_mode="SPOT",
        direction="LONG",
        size_base=0.5,
        entry_price=100.0,
        risk_amount=20.0,
    )
    assert state.size_base == 0.5
    assert ledger.get("BTC_USDT", "SPOT") is not None

    close = ledger.apply_close("BTC_USDT", "SPOT", close_size_base=0.2)
    assert close["closed_size_base"] == 0.2
    assert close["remaining_size_base"] == 0.3

    close_final = ledger.apply_close("BTC_USDT", "SPOT")
    assert close_final["closed_size_base"] == 0.3
    assert ledger.get("BTC_USDT", "SPOT") is None


def test_position_ledger_restore_from_journal(tmp_path):
    path = tmp_path / "journal.jsonl"
    entries = [
        {
            "symbol": "BTC_USDT",
            "direction": "LONG",
            "result": {
                "ledger_delta": {
                    "action": "ENTRY",
                    "symbol": "BTC_USDT",
                    "account_mode": "SPOT",
                    "direction": "LONG",
                    "size_base": 0.4,
                    "entry_price": 100.0,
                    "risk_amount": 10.0,
                }
            },
        },
        {
            "symbol": "BTC_USDT",
            "direction": "LONG",
            "result": {
                "ledger_delta": {
                    "action": "CLOSE",
                    "symbol": "BTC_USDT",
                    "account_mode": "SPOT",
                    "closed_size_base": 0.1,
                }
            },
        },
    ]
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")

    ledger = PositionLedger()
    ledger.restore_from_journal(str(path))
    position = ledger.get("BTC_USDT", "SPOT")
    assert position is not None
    assert round(position.size_base, 8) == 0.3

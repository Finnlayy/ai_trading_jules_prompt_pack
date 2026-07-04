from risk_gate_validator import validate_risk_gates


def _valid_payload():
    return {
        "signal_id": "sig-gate-1",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.0,
        "crisis_score": 10.0,
        "mc_dispersion": 2.0,
        "spread": 5.0,
    }


def test_validate_risk_gates_accepts_valid_signal():
    result = validate_risk_gates({"payload": _valid_payload()})

    assert result["ok"] is True
    assert result["decision"] == "PROCEED_TO_SIMULATION"
    assert result["reject_reasons"] == []
    assert result["metrics"]["risk_reward"] == 2.0


def test_validate_risk_gates_rejects_low_reward_risk():
    payload = _valid_payload()
    payload["target_price"] = 51000.0

    result = validate_risk_gates({"payload": payload})

    assert result["ok"] is False
    assert result["decision"] == "REJECT"
    assert "LOW_RR" in result["reject_reasons"]


def test_validate_risk_gates_rejects_duplicate_and_future_signal():
    payload = _valid_payload()

    result = validate_risk_gates(
        {
            "payload": payload,
            "context": {
                "seen_signal_ids": ["sig-gate-1"],
                "available_market_data_timestamp": "2026-05-20T09:59:00Z",
            },
        }
    )

    assert result["ok"] is False
    assert "DUPLICATE_SIGNAL" in result["reject_reasons"]
    assert "SIGNAL_AFTER_AVAILABLE_MARKET_DATA" in result["reject_reasons"]


def test_validate_risk_gates_rejects_invalid_ai_review_schema():
    result = validate_risk_gates(
        {
            "payload": _valid_payload(),
            "ai_review": {
                "schema_version": "1.0",
                "signal_id": "sig-gate-1",
                "decision": "EXECUTE_NOW",
                "confidence": 0.9,
                "reason_codes": [],
                "risk_flags": [],
                "requires_human_review": False,
            },
        }
    )

    assert result["ok"] is False
    assert result["decision"] == "REJECT"
    assert result["reject_reasons"] == ["SCHEMA_VALIDATION_FAILED"]


def test_validate_risk_gates_keeps_close_intent_available():
    payload = _valid_payload()
    payload.update(
        {
            "intent": "CLOSE",
            "confluence_score": 1.0,
            "crisis_score": 99.0,
            "spread": 99.0,
            "target_price": 49000.0,
        }
    )

    result = validate_risk_gates({"payload": payload})

    assert result["ok"] is True
    assert result["decision"] == "PROCEED_TO_SIMULATION"

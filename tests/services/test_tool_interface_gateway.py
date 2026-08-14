from tool_interface_gateway import dispatch_tool_request


def _valid_payload():
    return {
        "signal_id": "sig-gateway-1",
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


def test_gateway_dispatches_risk_validation():
    result = dispatch_tool_request(
        {
            "request_id": "req-1",
            "tool": "risk.validate",
            "payload": _valid_payload(),
        }
    )

    assert result["ok"] is True
    assert result["request_id"] == "req-1"
    assert result["result"]["decision"] == "PROCEED_TO_SIMULATION"


def test_gateway_rejects_unknown_tool():
    result = dispatch_tool_request(
        {
            "request_id": "req-unknown",
            "tool": "os.system",
            "payload": {},
        }
    )

    assert result["ok"] is False
    assert result["error_code"] == "UNKNOWN_TOOL"


def test_gateway_blocks_backend_forward_when_preflight_rejects():
    payload = _valid_payload()
    payload["target_price"] = 51000.0

    result = dispatch_tool_request(
        {
            "request_id": "req-preflight",
            "tool": "backend.m8",
            "payload": payload,
        }
    )

    assert result["ok"] is False
    assert result["status"] == "rejected"
    assert result["error_code"] == "RISK_GATE_REJECTED"
    assert "LOW_RR" in result["detail"]["reject_reasons"]


def test_gateway_blocks_expensive_optimizer_without_allow_flag():
    result = dispatch_tool_request(
        {
            "request_id": "req-ga",
            "tool": "ga_forward_optimizer",
            "payload": {},
        }
    )

    assert result["ok"] is False
    assert result["error_code"] == "EXPENSIVE_TOOL_REQUIRES_ALLOW_FLAG"

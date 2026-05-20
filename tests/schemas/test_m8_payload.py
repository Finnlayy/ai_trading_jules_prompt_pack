import pytest
from app.schemas.m8_payload import M8Payload
from pydantic import ValidationError

def test_valid_m8_payload():
    payload_data = {
        "signal_id": "sig-123",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.5,
        "crisis_score": 10.0,
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    payload = M8Payload(**payload_data)
    assert payload.signal_id == "sig-123"
    assert payload.direction == "LONG"
    assert payload.confluence_score == 85.5

def test_invalid_direction():
    payload_data = {
        "signal_id": "sig-123",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "INVALID_DIR",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.5,
        "crisis_score": 10.0,
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    with pytest.raises(ValidationError):
        M8Payload(**payload_data)

def test_invalid_confluence_score():
    payload_data = {
        "signal_id": "sig-123",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 105.0, # out of bounds
        "crisis_score": 10.0,
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    with pytest.raises(ValidationError):
        M8Payload(**payload_data)

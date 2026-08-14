from app.services.risk_engine import risk_engine_instance
from app.schemas.m8_payload import M8Payload
import pytest
from app.services.correlation_risk import CorrelationRiskChecker


def test_single_position_allowed():
    checker = CorrelationRiskChecker(max_per_sector=2)
    result = checker.check_new_entry("BTCUSDT", [])
    assert result["allowed"] is True
    assert result["sector"] == "CRYPTO"


def test_sector_limit_reached():
    checker = CorrelationRiskChecker(max_per_sector=2)
    open_pos = [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}]
    result = checker.check_new_entry("SOLUSDT", open_pos)
    assert result["allowed"] is False
    assert "CRYPTO" in result["reason"]
    assert result["current_count"] == 2


def test_different_sector_allowed():
    checker = CorrelationRiskChecker(max_per_sector=2)
    open_pos = [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}]
    result = checker.check_new_entry("XAGUSDT", open_pos)
    assert result["allowed"] is True
    assert result["sector"] == "METALS"


def test_unknown_sector_defaults_to_other():
    checker = CorrelationRiskChecker(max_per_sector=1)
    result = checker.check_new_entry("UNKNOWN_SYMBOL", [])
    assert result["allowed"] is True
    assert result["sector"] == "OTHER"

def test_volume_scaling_applied():
    payload = M8Payload(
        signal_id="sig-1",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        timestamp="2024-01-01T00:00:00Z",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        confluence_score=80.0,
        crisis_score=10.0,
        mc_dispersion=1.0,
        spread=1.0,
        execution_quantity=10.0
    )
    risk_engine_instance.open_positions = [{"symbol": "ETHUSDT"}]
    # max_per_sector is 2, current_count for CRYPTO is 1.
    # scale factor = 1.0 - (1 / 2) = 0.5
    # execution_quantity should be 10.0 * 0.5 = 5.0
    risk_engine_instance._gate_correlation_risk(payload)
    assert payload.execution_quantity == 5.0

def test_volume_scaling_no_other_positions():
    payload = M8Payload(
        signal_id="sig-2",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        timestamp="2024-01-01T00:00:00Z",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        confluence_score=80.0,
        crisis_score=10.0,
        mc_dispersion=1.0,
        spread=1.0,
        execution_quantity=10.0
    )
    risk_engine_instance.open_positions = []
    # current_count for CRYPTO is 0
    # No scaling should occur
    risk_engine_instance._gate_correlation_risk(payload)
    assert payload.execution_quantity == 10.0

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

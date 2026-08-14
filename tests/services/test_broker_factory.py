import pytest

from app.services.broker_factory import BrokerFactory
from app.services.broker import SimulationBroker
from app.services.paper_broker import PaperBroker
from app.services.pionex_relay_broker import PionexRelayBroker
from app.services.pionex_direct_broker import PionexDirectBroker
from app.services.glint_broker import GlintBroker
from app.services.ctrader_broker import CTraderBroker


def test_create_default_broker():
    """Test creating a broker without explicitly passing a mode."""
    # This should fallback to BROKER_MODE config, which defaults to 'simulation'
    broker = BrokerFactory.create()
    assert isinstance(broker, SimulationBroker)


@pytest.mark.parametrize("mode, expected_class", [
    ("simulation", SimulationBroker),
    ("sim", SimulationBroker),
    ("paper", PaperBroker),
    ("pionex_relay", PionexRelayBroker),
    ("relay", PionexRelayBroker),
    ("pionex", PionexRelayBroker),
    ("pionex_direct", PionexDirectBroker),
    ("direct", PionexDirectBroker),
    ("pionex_api", PionexDirectBroker),
    ("glint", GlintBroker),
    ("ctrader", CTraderBroker),
    ("ctrader_direct", CTraderBroker),
])
def test_create_broker_modes(mode, expected_class):
    """Test all explicitly supported broker creation modes."""
    broker = BrokerFactory.create(mode=mode)
    assert isinstance(broker, expected_class)


def test_create_broker_fallback():
    """Test that invalid modes fallback to SimulationBroker."""
    broker = BrokerFactory.create(mode="invalid_unknown_mode_123")
    assert isinstance(broker, SimulationBroker)


@pytest.mark.parametrize("mode, expected_valid", [
    ("simulation", True),
    ("sim", False), # 'sim' maps to SimulationBroker in create() but isn't explicitly in _VALID_SINGLE_MODES list for is_valid_mode()
    ("paper", True),
    ("pionex_relay", True),
    ("invalid", False),
    ("", False),
])
def test_is_valid_mode(mode, expected_valid):
    """Test validation of broker modes based on _VALID_SINGLE_MODES."""
    assert BrokerFactory.is_valid_mode(mode) == expected_valid


def test_available_modes():
    """Test retrieving available modes."""
    modes = BrokerFactory.available_modes()
    assert isinstance(modes, list)
    assert "simulation" in modes
    assert "paper" in modes
    assert "pionex_direct" in modes


@pytest.mark.parametrize("mode, expected_name", [
    ("simulation", "Simulation"),
    ("paper", "Paper Trading"),
    ("pionex_relay", "Pionex Relay"),
    ("pionex_direct", "Pionex Direct"),
    ("glint", "GLINT (Hyperliquid)"),
    ("ctrader", "cTrader Direct"),
    ("unknown_mode", "unknown_mode"), # Should fallback to itself if unknown
])
def test_mode_display_name(mode, expected_name):
    """Test that the display name maps correctly."""
    assert BrokerFactory.mode_display_name(mode) == expected_name

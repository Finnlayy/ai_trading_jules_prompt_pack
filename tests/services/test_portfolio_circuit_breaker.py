import pytest
from app.services.portfolio_circuit_breaker import PortfolioCircuitBreaker


@pytest.fixture
def breaker(tmp_path):
    return PortfolioCircuitBreaker(
        max_daily_drawdown_pct=5.0,
        filepath=str(tmp_path / "circuit.json"),
    )


def test_initial_state_allows_trading(breaker):
    cb = breaker.check_trade_allowed()
    assert cb["trade_allowed"] is True
    assert cb["halted"] is False
    assert cb["drawdown_pct"] == 0.0


def test_set_starting_balance(breaker):
    breaker.set_starting_balance(10000.0)
    state = breaker.get_state()
    assert state["starting_balance"] == 10000.0
    assert state["high_watermark"] == 10000.0


def test_record_winning_trade(breaker):
    breaker.set_starting_balance(10000.0)
    result = breaker.record_trade_pnl(500.0)
    assert result["trade_allowed"] is True
    assert result["halt_triggered"] is False
    state = breaker.get_state()
    assert state["realized_pnl"] == 500.0
    assert state["high_watermark"] == 10500.0


def test_record_losing_trade_triggers_halt(breaker):
    breaker.set_starting_balance(10000.0)
    result = breaker.record_trade_pnl(-600.0)
    assert result["trade_allowed"] is False
    assert result["halt_triggered"] is True
    assert "6.00%" in result["reason"] or "5.00%" in result["reason"]


def test_halt_persists_after_trigger(breaker):
    breaker.set_starting_balance(10000.0)
    breaker.record_trade_pnl(-600.0)
    cb = breaker.check_trade_allowed()
    assert cb["trade_allowed"] is False
    assert cb["halted"] is True


def test_reset_clears_state(breaker):
    breaker.set_starting_balance(10000.0)
    breaker.record_trade_pnl(-600.0)
    breaker.reset()
    cb = breaker.check_trade_allowed()
    assert cb["trade_allowed"] is True
    assert cb["halted"] is False


def test_persistence(tmp_path):
    path = tmp_path / "persist.json"
    b1 = PortfolioCircuitBreaker(max_daily_drawdown_pct=5.0, filepath=str(path))
    b1.set_starting_balance(10000.0)
    b1.record_trade_pnl(200.0)

    b2 = PortfolioCircuitBreaker(max_daily_drawdown_pct=5.0, filepath=str(path))
    state = b2.get_state()
    assert state["starting_balance"] == 10000.0
    assert state["realized_pnl"] == 200.0


def test_drawdown_from_high_watermark_not_starting_balance(breaker):
    breaker.set_starting_balance(10000.0)
    breaker.record_trade_pnl(1000.0)   # equity = 11000, hwm = 11000
    breaker.record_trade_pnl(-300.0)   # equity = 10700, dd = 300/11000 = 2.7%
    cb = breaker.check_trade_allowed()
    assert cb["trade_allowed"] is True  # 2.7% < 5%

    breaker.record_trade_pnl(-900.0)   # equity = 9800, dd = 1200/11000 = 10.9%
    cb = breaker.check_trade_allowed()
    assert cb["trade_allowed"] is False

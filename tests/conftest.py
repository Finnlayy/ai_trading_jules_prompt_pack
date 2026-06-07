import os


# Keep tests deterministic regardless of local .env content.
os.environ["AI_PROVIDER"] = "moonshot"
os.environ["AI_REVIEW_ENGINE"] = "legacy6"
os.environ["BROKER_MODE"] = "simulation"
os.environ["PAPER_TRADING_RELAX_RISK"] = "false"
os.environ["PIONEX_RELAY_ENABLED"] = "false"
os.environ["PIONEX_DIRECT_ENABLED"] = "false"
os.environ["PIONEX_DIRECT_LIVE_TRADING_ENABLED"] = "false"
os.environ["AI_FAILURE_POLICY"] = "reject_live"
os.environ["WEBHOOK_SECRET"] = ""
os.environ["MIN_CONFLUENCE_SCORE"] = "70"
os.environ["ACADEMY_POLICY_MODE"] = "shadow"
os.environ["ACADEMY_POLICY_BACKEND"] = "heuristic"
os.environ["ACADEMY_POLICY_CYCLE_DECISIONS"] = "16"


import pytest


@pytest.fixture(autouse=True)
def reset_webhook_secret_config():
    """Keep webhook auth config isolated between tests that mutate globals."""
    import app.core.config as config_module

    default_secret = os.environ.get("WEBHOOK_SECRET", "")
    config_module.WEBHOOK_SECRET = default_secret
    yield
    config_module.WEBHOOK_SECRET = default_secret


@pytest.fixture(autouse=True)
def mock_regime_check(monkeypatch):
    """Patch regime check to always allow trades in tests."""
    async def _mock_check_regime(payload):
        return {"trade_allowed": True, "regime": "TEST", "reason": "Mocked for tests"}
    monkeypatch.setattr("app.api.orchestrator._check_regime", _mock_check_regime)

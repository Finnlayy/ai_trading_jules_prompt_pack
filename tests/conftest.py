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


# Force DB initialization using app.data.trading.db
import os
os.environ["DATABASE_URL"] = "sqlite:///./app/data/trading.db"
from app.db import engine, Base
Base.metadata.create_all(bind=engine)


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










@pytest.fixture(autouse=True)
def mock_webhook_signature_check(monkeypatch, request):
    """Globally mock webhook signature checks for all business-logic tests,
    but allow actual signature-validation tests to run cleanly.
    """
    if "test_webhook_signal" in getattr(request.module, "__name__", "") or "test_endpoints" in getattr(request.module, "__name__", ""):
        yield
    else:
        try:
            import app.api.endpoints
            import app.api.webhook_signal
            import app.core.config

            # Use monkeypatch.setitem on os.environ to ensure config picks it up
            # when re-evaluating, AND override the current config values directly
            import os
            monkeypatch.setitem(os.environ, "WEBHOOK_SECRET", "test-secret-do-not-use")
            monkeypatch.setattr(app.core.config, "WEBHOOK_SECRET", "test-secret-do-not-use")
            monkeypatch.setattr(app.api.endpoints.config, "WEBHOOK_SECRET", "test-secret-do-not-use")
            monkeypatch.setattr(app.api.webhook_signal.config, "WEBHOOK_SECRET", "test-secret-do-not-use")

            monkeypatch.setattr("app.api.endpoints._verify_webhook_signature", lambda body, sig: True)
            monkeypatch.setattr("app.api.webhook_signal._verify_signature", lambda body, sig, secret: True)

            monkeypatch.setattr(app.core.config, "_TESTING_ENABLE_WEBHOOK_SIG_CHECK", False, raising=False)

        except Exception as e:
            pass

        yield

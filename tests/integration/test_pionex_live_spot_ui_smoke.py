import pytest
import os
import asyncio
from unittest.mock import patch, MagicMock
from app.api.endpoints import router
from app.api.orchestrator import _build_broker, reset_broker
import app.core.config as app_core_config_module
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_pionex_live_spot_smoke_skipped_by_default():
    """
    Live tests should only run if intentionally triggered via environment variables.
    """
    run_live = os.getenv("RUN_LIVE_PIONEX_TESTS") == "true"
    confirmation = os.getenv("PIONEX_LIVE_TEST_CONFIRMATION") == "I_UNDERSTAND_THIS_PLACES_REAL_PIONEX_ORDERS"

    if not (run_live and confirmation):
        pytest.skip("Live Pionex spot tests are skipped by default for safety.")

    assert True

# Optional: Add actual live execution here if credentials are given,
# ensuring to auto-close and limit the order size strictly to max 5 USDT.

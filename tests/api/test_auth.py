from fastapi.testclient import TestClient
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app.main import app

client = TestClient(app)

def test_auth_unauthorized():
    response = client.get("/backtest/some_route") # Testing dependency
    assert response.status_code in [401, 403, 404]


def test_public_config_returns_google_client_id_field():
    """The public config endpoint must be unauthenticated and expose googleClientId."""
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    body = response.json()
    assert "googleClientId" in body
    assert isinstance(body["googleClientId"], str)


def test_public_config_reflects_configured_client_id(monkeypatch):
    """The endpoint should surface the configured GOOGLE_CLIENT_ID at runtime."""
    import app.api.auth as auth_module

    monkeypatch.setattr(auth_module, "GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    assert response.json()["googleClientId"] == "test-client.apps.googleusercontent.com"

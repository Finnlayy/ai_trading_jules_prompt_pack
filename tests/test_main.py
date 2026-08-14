import pytest
from fastapi.testclient import TestClient

def test_health_check(monkeypatch):
    """Test the /health endpoint (requires a configured API key + X-API-Key header)."""
    monkeypatch.setenv("API_KEY", "test-api-key")
    from app.main import app
    client = TestClient(app)
    response = client.get("/health", headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_rejects_missing_key(monkeypatch):
    """/health must reject requests without a valid X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-api-key")
    from app.main import app
    client = TestClient(app)
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-API-Key": "wrong"}).status_code == 401

def test_frontend():
    """Test the root endpoint serving frontend.html."""
    from app.main import app
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")

def test_favicon():
    """Test the /favicon.ico endpoint."""
    from app.main import app
    client = TestClient(app)
    response = client.get("/favicon.ico")
    assert response.status_code == 204

def test_lifecycle_events():
    """Test application startup and shutdown events using TestClient context manager."""
    from app.main import app
    import app.main as main_module

    # We mock Base.metadata.create_all to avoid attempting to create tables
    # during this basic test if it accesses a live DB, but standard pytest mock or relying on test DB is fine.
    # The context manager triggers 'startup' and then 'shutdown' when it exits.
    with TestClient(app) as test_client:
        # Check that tasks were created on startup
        assert main_module._heartbeat_task is not None
        assert main_module._news_poll_task is not None
        assert main_module._autostart_task is not None
        assert main_module._shadow_queue_task is not None

        # We don't need to do anything inside, just verifying it doesn't crash
        pass

    # Check that tasks were cancelled on shutdown
    assert main_module._heartbeat_task.cancelled() or main_module._heartbeat_task.done()
    assert main_module._news_poll_task.cancelled() or main_module._news_poll_task.done()
    assert main_module._autostart_task.cancelled() or main_module._autostart_task.done()
    assert main_module._shadow_queue_task.cancelled() or main_module._shadow_queue_task.done()

def test_cors_middleware():
    """Test that CORS middleware is applied and returns correct headers."""
    from app.main import app
    client = TestClient(app)
    response = client.options("/health", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    # Since CORS_ORIGINS is empty by default, a random origin like localhost:3000 will be rejected (400) by the preflight.
    # We assert 400 to verify the middleware is active and correctly blocking unconfigured origins.
    assert response.status_code == 400
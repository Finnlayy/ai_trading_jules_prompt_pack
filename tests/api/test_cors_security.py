import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import get_api_key

def test_cors_origin_is_restricted_by_default():
    """
    Test that the default CORS configuration is secure.
    By default, CORS_ORIGINS should be an empty list (unless overridden by env),
    meaning cross-origin requests should NOT include the 'access-control-allow-origin' header.
    """
    app.dependency_overrides[get_api_key] = lambda: "dummy_key"
    client = TestClient(app)

    # Send a cross-origin request to an existing endpoint
    response = client.get("/health", headers={"Origin": "http://evil.com"})

    # 200 OK because the endpoint itself doesn't block the request,
    # but the browser blocks it if CORS headers are missing.
    assert response.status_code == 200

    # The secure outcome is the ABSENCE of the CORS headers allowing the origin.
    assert "access-control-allow-origin" not in response.headers
    app.dependency_overrides.clear()

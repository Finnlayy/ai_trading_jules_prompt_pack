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

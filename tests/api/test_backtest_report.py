"""Epic 3 Task 3.5 — Reporting API with aggregated backtest metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_backtest_report_returns_metrics():
    """GET /backtest/report must return aggregated metrics as clean JSON."""
    response = client.get("/backtest/report?symbol=SOLUSD&days=7")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "metrics" in data
    metrics = data["metrics"]

    # Required fields
    assert "winrate_pct" in metrics
    assert "max_drawdown_pct" in metrics
    assert "avg_slippage_pct" in metrics
    assert "total_trades" in metrics
    assert "profit_factor" in metrics

    # Sanity checks
    assert 0 <= metrics["winrate_pct"] <= 100
    assert metrics["total_trades"] >= 0

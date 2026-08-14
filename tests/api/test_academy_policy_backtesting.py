from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import academy as academy_module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(academy_module.router)
    return TestClient(app)


def _records(count: int = 24) -> list[dict[str, float | int | str]]:
    rows = []
    for idx in range(count):
        close = 100.0 + idx
        rows.append({
            "timestamp": f"2026-06-01T12:{idx:02d}:00Z",
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000.0 + idx,
            "scout_index": 3,
            "difficulty": 2,
            "total_reward": 0.8,
            "accuracy": 0.75,
            "calibration": 0.7,
            "ab_lift": 0.03,
        })
    return rows


def test_academy_policy_backtesting_run_vectorbt_returns_serialized_metrics():
    client = _client()

    response = client.post(
        "/academy/policy/backtesting/run",
        json={
            "backend": "vectorbt",
            "records": _records(),
            "params": {
                "target_scout_index": 3,
                "min_reward": 0.2,
                "min_accuracy": 0.6,
                "initial_cash": 10000.0,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["backend"] == "vectorbt"
    assert set(data["metrics"]) == {"sharpe_ratio", "max_drawdown", "calmar_ratio", "total_return"}
    assert len(data["equity_curve"]) == 24
    assert len(data["drawdown_curve"]) == 24


def test_academy_policy_backtesting_run_backtrader_returns_same_contract():
    client = _client()

    response = client.post(
        "/academy/policy/backtesting/run",
        json={
            "backend": "backtrader",
            "records": _records(),
            "params": {
                "target_scout_index": 3,
                "min_reward": 0.2,
                "min_accuracy": 0.6,
                "initial_cash": 10000.0,
                "size": 10.0,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["backend"] == "backtrader"
    assert isinstance(data["positions"], list)
    assert len(data["equity_curve"]) == 24


def test_academy_policy_backtesting_optimize_uses_scipy_minimize():
    client = _client()

    response = client.post(
        "/academy/policy/backtesting/optimize",
        json={
            "records": _records(12),
            "initial_params": {
                "target_scout_index": 3,
                "min_reward": 0.1,
                "min_accuracy": 0.5,
                "initial_cash": 10000.0,
            },
            "weights": {"sharpe": 0.5, "drawdown": 0.3, "calmar": 0.2},
            "method": "minimize",
            "maxiter": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["method"] == "minimize"
    assert "optimal_params" in data
    assert "metrics" in data


def test_academy_policy_backtesting_grid_search_returns_rows():
    client = _client()

    response = client.post(
        "/academy/policy/backtesting/grid-search",
        json={
            "records": _records(12),
            "param_grid": {
                "target_scout_index": [3],
                "min_reward": [0.0, 0.4],
                "min_accuracy": [0.5, 0.7],
                "initial_cash": [10000.0],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["row_count"] == 4
    assert len(data["results"]) == 4


def test_academy_policy_backtesting_rejects_empty_records():
    client = _client()

    response = client.post(
        "/academy/policy/backtesting/run",
        json={"backend": "vectorbt", "records": [], "params": {}},
    )

    assert response.status_code == 422


def test_academy_policy_backtesting_report_writes_png_charts(tmp_path, monkeypatch):
    monkeypatch.setattr(academy_module, "REPORTS_DIR", tmp_path)
    client = _client()

    response = client.post(
        "/academy/policy/backtesting/report",
        json={
            "backend": "vectorbt",
            "records": _records(),
            "params": {
                "target_scout_index": 3,
                "min_reward": 0.2,
                "min_accuracy": 0.6,
                "initial_cash": 10000.0,
            },
            "include_charts": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["charts"]) >= 2
    for chart in data["charts"]:
        filename = chart["path"].rsplit("/", 1)[-1]
        assert (Path(tmp_path) / filename).exists()
        assert chart["path"].startswith("/academy/policy/backtesting/reports/")

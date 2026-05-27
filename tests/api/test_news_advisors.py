from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import news
from app.main import app


@pytest.mark.asyncio
async def test_glint_ask_uses_advisor_hub(monkeypatch):
    monkeypatch.setattr(
        news.telegram_advisor_hub,
        "ask_glint",
        AsyncMock(
            return_value={
                "configured": True,
                "sent": True,
                "timed_out": False,
                "messages": [{"id": 1, "text": "positions ok", "sender": "glint"}],
            }
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/news/glint/ask?question=Positions")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["new_count"] == 1


@pytest.mark.asyncio
async def test_manus_ask_reports_not_configured(monkeypatch):
    monkeypatch.setattr(
        news.telegram_advisor_hub,
        "ask_manus",
        AsyncMock(
            return_value={
                "configured": False,
                "sent": False,
                "timed_out": False,
                "messages": [],
                "error": "not configured",
            }
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/news/manus/ask?question=hello")

    assert response.status_code == 200
    assert response.json()["status"] == "error"

"""News API endpoints for MSN Finance, Yahoo Finance, and GLINT.trade feeds."""
from __future__ import annotations

from fastapi import APIRouter

from app.services.news_aggregator import news_aggregator_instance
from app.services.telegram_news_receiver import telegram_news_receiver_instance

router = APIRouter()


@router.get("/feed")
async def get_news_feed(source: str = "all"):
    """Fetch latest RSS news from MSN Finance and/or Yahoo Finance.

    Query params:
        source: "msn" | "yahoo" | "all" (default)
    """
    try:
        items = await news_aggregator_instance.fetch(source=source)
    except Exception as e:
        return {"status": "error", "detail": str(e), "items": []}

    return {
        "status": "ok",
        "source": source,
        "count": len(items),
        "last_fetch": news_aggregator_instance.last_fetch_iso(),
        "items": [
            {
                "source": it.source,
                "title": it.title,
                "link": it.link,
                "published": it.published,
                "summary": it.summary,
            }
            for it in items
        ],
    }


@router.get("/feed/cached")
async def get_cached_news():
    """Return cached news without hitting the network."""
    items = news_aggregator_instance.get_cached()
    return {
        "status": "ok",
        "count": len(items),
        "last_fetch": news_aggregator_instance.last_fetch_iso(),
        "items": [
            {
                "source": it.source,
                "title": it.title,
                "link": it.link,
                "published": it.published,
                "summary": it.summary,
            }
            for it in items
        ],
    }


@router.get("/glint")
async def get_glint_messages():
    """Return stored GLINT messages from Telegram feed."""
    messages = telegram_news_receiver_instance.get_messages()
    return {
        "status": "ok",
        "count": len(messages),
        "receiver_status": telegram_news_receiver_instance.status(),
        "messages": [
            {
                "id": m.id,
                "text": m.text,
                "sender": m.sender,
                "timestamp": m.timestamp,
            }
            for m in messages
        ],
    }


@router.post("/glint/poll")
async def poll_glint_messages():
    """Manually trigger a Telegram poll and return new messages."""
    new_messages = await telegram_news_receiver_instance.poll_async()
    return {
        "status": "ok",
        "new_count": len(new_messages),
        "total_stored": len(telegram_news_receiver_instance.get_messages()),
        "messages": [
            {
                "id": m.id,
                "text": m.text,
                "sender": m.sender,
                "timestamp": m.timestamp,
            }
            for m in new_messages
        ],
    }

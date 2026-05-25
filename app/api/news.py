"""News API endpoints for MSN Finance, Yahoo Finance, and GLINT.trade feeds."""
from __future__ import annotations

from fastapi import APIRouter

from app.services.news_aggregator import news_aggregator_instance
from app.services.telegram_news_receiver import (
    telegram_news_receiver_instance,
    manus_telegram_receiver_instance,
)
from app.services.telegram_advisors import telegram_advisor_hub

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
                "chat_id": m.chat_id,
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
                "chat_id": m.chat_id,
            }
            for m in new_messages
        ],
    }


@router.post("/glint/ask")
async def ask_glint(question: str = "Positions"):
    """Ask GLINT a harmless status-style question and wait briefly for a response."""
    result = await telegram_advisor_hub.ask_glint(question)
    if not result["configured"]:
        return {"status": "error", "detail": "GLINT not configured. Set GLINT_TELEGRAM_CHAT_ID and GLINT_BOT_USERNAME."}
    if not result["sent"]:
        return {"status": "error", "detail": result.get("error") or "Failed to send message to GLINT chat."}
    return {
        "status": "ok",
        "question": question,
        "sent": result["sent"],
        "timed_out": result["timed_out"],
        "new_count": len(result["messages"]),
        "messages": result["messages"],
    }


# ------------------------------------------------------------------
# Manus advisor feed endpoints (separate Telegram chat)
# ------------------------------------------------------------------

@router.get("/manus")
async def get_manus_messages():
    """Return stored Manus advisor messages from separate Telegram feed."""
    messages = manus_telegram_receiver_instance.get_messages()
    return {
        "status": "ok",
        "count": len(messages),
        "receiver_status": manus_telegram_receiver_instance.status(),
        "messages": [
            {
                "id": m.id,
                "text": m.text,
                "sender": m.sender,
                "timestamp": m.timestamp,
                "chat_id": m.chat_id,
            }
            for m in messages
        ],
    }


@router.post("/manus/poll")
async def poll_manus_messages():
    """Manually trigger a Manus Telegram poll and return new messages."""
    new_messages = await manus_telegram_receiver_instance.poll_async()
    return {
        "status": "ok",
        "new_count": len(new_messages),
        "total_stored": len(manus_telegram_receiver_instance.get_messages()),
        "messages": [
            {
                "id": m.id,
                "text": m.text,
                "sender": m.sender,
                "timestamp": m.timestamp,
                "chat_id": m.chat_id,
            }
            for m in new_messages
        ],
    }


@router.post("/manus/ask")
async def ask_manus(question: str):
    """Send a question to the Manus advisor bot and wait for response."""
    result = await telegram_advisor_hub.ask_manus(question)
    if not result["configured"]:
        return {"status": "error", "detail": "Manus not configured. Set MANUS_TELEGRAM_CHAT_ID and MANUS_BOT_USERNAME."}
    if not result["sent"]:
        return {"status": "error", "detail": result.get("error") or "Failed to send message to Manus chat."}
    return {
        "status": "ok",
        "question": question,
        "sent": result["sent"],
        "timed_out": result["timed_out"],
        "new_messages_count": len(result["messages"]),
        "messages": result["messages"],
    }

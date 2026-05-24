"""Telegram message receiver for GLINT.trade feed ingestion.

How it works:
1. Create a Telegram channel/group.
2. Add the GLINT bot (or forward GLINT messages) to that channel.
3. Add your own bot to the same channel.
4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.
5. This receiver polls getUpdates and filters messages from that chat.

Messages are stored in a ring buffer and served via API.
"""
from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import httpx

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class GlintMessage:
    id: int
    text: str
    sender: str
    timestamp: str
    chat_id: str


class TelegramNewsReceiver:
    """Polls Telegram for messages and stores GLINT feed items."""

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        max_messages: int = 100,
        poll_interval_seconds: float = 30.0,
    ) -> None:
        self.bot_token = bot_token or _env("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or _env("TELEGRAM_CHAT_ID", "")
        self.max_messages = max_messages
        self.poll_interval = poll_interval_seconds
        self._messages: deque = deque(maxlen=max_messages)
        self._last_update_id: Optional[int] = None
        self._enabled = bool(self.bot_token and self.chat_id)
        self._client: Optional[httpx.AsyncClient] = None

    def _client_sync(self) -> httpx.Client:
        return httpx.Client(timeout=15.0)

    def _client_async(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    def _url(self, method: str) -> str:
        return f"{TELEGRAM_API_BASE.format(token=self.bot_token)}/{method}"

    def _is_configured(self) -> bool:
        return self._enabled

    def _matches_chat(self, message_chat_id: int | str) -> bool:
        """Check if message belongs to our monitored chat."""
        if not self.chat_id:
            return False
        # chat_id can be negative for groups/channels
        return str(message_chat_id) == str(self.chat_id)

    def _extract_text(self, msg: dict) -> str:
        """Extract text from message (handles text, caption, edited_message)."""
        if "text" in msg:
            return msg["text"]
        if "caption" in msg:
            return msg["caption"]
        # Forwarded messages might have different structure
        return ""

    def _extract_sender(self, msg: dict) -> str:
        from_user = msg.get("from", {})
        username = from_user.get("username", "")
        first = from_user.get("first_name", "")
        last = from_user.get("last_name", "")
        return username or f"{first} {last}".strip() or "Unknown"

    def poll_sync(self, limit: int = 20) -> List[GlintMessage]:
        """Synchronous poll — useful for startup hydration."""
        if not self._is_configured():
            return []
        try:
            with self._client_sync() as client:
                params: dict = {"limit": limit}
                if self._last_update_id is not None:
                    params["offset"] = self._last_update_id + 1
                response = client.get(self._url("getUpdates"), params=params)
                response.raise_for_status()
                data = response.json()
                return self._process_updates(data.get("result", []))
        except Exception:
            return []

    async def poll_async(self, limit: int = 20) -> List[GlintMessage]:
        """Async poll — for background tasks."""
        if not self._is_configured():
            return []
        try:
            client = self._client_async()
            params: dict = {"limit": limit}
            if self._last_update_id is not None:
                params["offset"] = self._last_update_id + 1
            response = await client.get(self._url("getUpdates"), params=params)
            response.raise_for_status()
            data = response.json()
            return self._process_updates(data.get("result", []))
        except Exception:
            return []

    def _process_updates(self, updates: list) -> List[GlintMessage]:
        new_messages: List[GlintMessage] = []
        for update in updates:
            self._last_update_id = max(self._last_update_id or 0, update.get("update_id", 0))
            msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
            if not msg:
                continue
            chat = msg.get("chat", {})
            chat_id = chat.get("id", "")
            if not self._matches_chat(chat_id):
                continue
            text = self._extract_text(msg)
            if not text:
                continue
            gm = GlintMessage(
                id=msg.get("message_id", 0),
                text=text,
                sender=self._extract_sender(msg),
                timestamp=datetime.now(timezone.utc).isoformat(),
                chat_id=str(chat_id),
            )
            self._messages.append(gm)
            new_messages.append(gm)
        return new_messages

    def get_messages(self, limit: int = 50) -> List[GlintMessage]:
        """Return stored messages newest first."""
        msgs = list(self._messages)
        msgs.reverse()
        return msgs[:limit]

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "configured": self._is_configured(),
            "chat_id": self.chat_id[:4] + "****" if self.chat_id else "",
            "stored_messages": len(self._messages),
            "last_update_id": self._last_update_id,
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global singletons (lazy config from env)
from app.core.config import TELEGRAM_BOT_TOKEN, GLINT_TELEGRAM_CHAT_ID, MANUS_TELEGRAM_CHAT_ID

# GLINT receiver — monitors GLINT bot messages (uses GLINT-specific chat ID)
telegram_news_receiver_instance = TelegramNewsReceiver(
    bot_token=TELEGRAM_BOT_TOKEN,
    chat_id=GLINT_TELEGRAM_CHAT_ID,
    max_messages=100,
)

# Manus receiver — monitors Manus advisor bot messages (separate chat)
manus_telegram_receiver_instance = TelegramNewsReceiver(
    bot_token=TELEGRAM_BOT_TOKEN,
    chat_id=MANUS_TELEGRAM_CHAT_ID,
    max_messages=100,
)

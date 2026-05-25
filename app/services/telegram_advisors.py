from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any

from app.core.config import (
    AI_TELEGRAM_ADVISORS_ENABLED,
    AI_TELEGRAM_ADVISOR_TIMEOUT_SECONDS,
    GLINT_BOT_USERNAME,
    GLINT_ENABLED,
    GLINT_TELEGRAM_CHAT_ID,
    MANUS_BOT_USERNAME,
    MANUS_ENABLED,
    MANUS_TELEGRAM_CHAT_ID,
    TELEGRAM_BOT_TOKEN,
)
from app.services.telegram_news_receiver import (
    GlintMessage,
    manus_telegram_receiver_instance,
    telegram_news_receiver_instance,
)
from app.services.telegram_notifier import TelegramConfig, TelegramNotifier


@dataclass(frozen=True)
class AdvisorAskResult:
    advisor: str
    enabled: bool
    configured: bool
    sent: bool
    timed_out: bool
    question: str
    messages: list[dict[str, Any]]
    error: str = ""


class TelegramAdvisorHub:
    """Ask Telegram-backed advisors and collect their next response."""

    def __init__(self) -> None:
        self.auto_enabled = AI_TELEGRAM_ADVISORS_ENABLED
        self.timeout_seconds = AI_TELEGRAM_ADVISOR_TIMEOUT_SECONDS

    def status(self) -> dict[str, Any]:
        return {
            "auto_enabled": self.auto_enabled,
            "timeout_seconds": self.timeout_seconds,
            "glint": {
                "enabled": GLINT_ENABLED,
                "configured": telegram_news_receiver_instance._is_configured(),
                "bot_username": GLINT_BOT_USERNAME,
            },
            "manus": {
                "enabled": MANUS_ENABLED,
                "configured": manus_telegram_receiver_instance._is_configured(),
                "bot_username": MANUS_BOT_USERNAME,
            },
        }

    async def ask_glint(
        self,
        question: str = "Positions",
        *,
        require_enabled: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return asdict(
            await self._ask(
                advisor="glint",
                enabled=GLINT_ENABLED,
                receiver=telegram_news_receiver_instance,
                chat_id=GLINT_TELEGRAM_CHAT_ID,
                bot_username=GLINT_BOT_USERNAME,
                question=question,
                require_enabled=require_enabled,
                timeout_seconds=timeout_seconds,
            )
        )

    async def ask_manus(
        self,
        question: str,
        *,
        require_enabled: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return asdict(
            await self._ask(
                advisor="manus",
                enabled=MANUS_ENABLED,
                receiver=manus_telegram_receiver_instance,
                chat_id=MANUS_TELEGRAM_CHAT_ID,
                bot_username=MANUS_BOT_USERNAME,
                question=question,
                require_enabled=require_enabled,
                timeout_seconds=timeout_seconds,
            )
        )

    async def ask_signal_advisors(self, manus_question: str) -> dict[str, Any]:
        if not self.auto_enabled:
            return {"auto_enabled": False, "advisors": []}

        tasks = []
        if MANUS_ENABLED:
            tasks.append(
                self.ask_manus(
                    manus_question,
                    require_enabled=True,
                    timeout_seconds=self.timeout_seconds,
                )
            )
        if GLINT_ENABLED:
            tasks.append(
                self.ask_glint(
                    "Positions",
                    require_enabled=True,
                    timeout_seconds=min(self.timeout_seconds, 15.0),
                )
            )

        if not tasks:
            return {"auto_enabled": True, "advisors": []}

        results = await asyncio.gather(*tasks, return_exceptions=True)
        advisors = []
        for result in results:
            if isinstance(result, Exception):
                advisors.append(
                    {
                        "advisor": "unknown",
                        "enabled": True,
                        "configured": False,
                        "sent": False,
                        "timed_out": False,
                        "question": "",
                        "messages": [],
                        "error": str(result),
                    }
                )
            else:
                advisors.append(result)
        return {"auto_enabled": True, "advisors": advisors}

    async def _ask(
        self,
        *,
        advisor: str,
        enabled: bool,
        receiver,
        chat_id: str,
        bot_username: str,
        question: str,
        require_enabled: bool,
        timeout_seconds: float | None,
    ) -> AdvisorAskResult:
        configured = bool(TELEGRAM_BOT_TOKEN and chat_id and receiver._is_configured())
        if require_enabled and not enabled:
            return AdvisorAskResult(advisor, enabled, configured, False, False, question, [])
        if not configured:
            return AdvisorAskResult(
                advisor,
                enabled,
                configured,
                False,
                False,
                question,
                [],
                error=f"{advisor.upper()} Telegram advisor is not configured",
            )

        # Drain stale updates first so the response window starts after our question.
        await receiver.poll_async(limit=20)

        notifier = TelegramNotifier(
            TelegramConfig(
                enabled=True,
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=chat_id,
            )
        )
        sent = await asyncio.to_thread(notifier.send, question)
        if not sent:
            return AdvisorAskResult(
                advisor,
                enabled,
                configured,
                False,
                False,
                question,
                [],
                error=f"Failed to send question to {advisor}",
            )

        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        deadline = time.monotonic() + max(timeout, 0.0)
        matched: list[GlintMessage] = []

        while time.monotonic() <= deadline:
            new_messages = await receiver.poll_async(limit=20)
            matched.extend(
                message
                for message in new_messages
                if self._message_matches(message, bot_username, question)
            )
            if matched:
                return AdvisorAskResult(
                    advisor,
                    enabled,
                    configured,
                    True,
                    False,
                    question,
                    [self._message_to_dict(message) for message in matched],
                )
            await asyncio.sleep(2.0)

        return AdvisorAskResult(advisor, enabled, configured, True, True, question, [])

    @staticmethod
    def _message_matches(message: GlintMessage, bot_username: str, question: str) -> bool:
        if message.text.strip() == question.strip():
            return False
        if not bot_username:
            return True
        return message.sender.lower().lstrip("@") == bot_username.lower().lstrip("@")

    @staticmethod
    def _message_to_dict(message: GlintMessage) -> dict[str, Any]:
        return {
            "id": message.id,
            "text": message.text,
            "sender": message.sender,
            "timestamp": message.timestamp,
            "chat_id": message.chat_id,
        }


telegram_advisor_hub = TelegramAdvisorHub()

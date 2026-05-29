"""FastAPI router for external trading signal webhooks.

Validates HMAC-SHA256 signatures and enforces Pydantic schema
before queuing signals for the autonomous loop or paper broker.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import WEBHOOK_SECRET
from app.schemas.webhook_signal import WebhookSignalPayload, WebhookSignalResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify HMAC-SHA256 hex signature against raw request body."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/signal", response_model=WebhookSignalResponse)
async def receive_signal(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> dict[str, Any]:
    """Receive an external trading signal with HMAC verification.

    Args:
        request: Raw FastAPI request to read body bytes.
        x_signature: HMAC-SHA256 hex signature of the JSON payload.

    Returns:
        Acknowledgement with generated signal_id.
    """
    body = await request.body()

    # Validate signature if a webhook secret is configured
    if WEBHOOK_SECRET:
        if not x_signature:
            raise HTTPException(status_code=401, detail="Missing X-Signature header")
        if not _verify_signature(body, x_signature, WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and validate payload schema
    try:
        payload = WebhookSignalPayload.model_validate_json(body)
    except Exception as exc:
        logger.warning("Webhook signal schema validation failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Schema validation failed: {exc}") from exc

    signal_id = f"sig_{uuid.uuid4().hex[:12]}"
    logger.info("Received signal %s: %s %s", signal_id, payload.direction, payload.symbol)

    # TODO (Epic 2.2+): Queue signal for autonomous loop or paper broker

    return {
        "status": "ok",
        "signal_id": signal_id,
        "message": f"Signal accepted: {payload.direction} {payload.symbol}",
    }

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from app.schemas.m8_payload import M8Payload
from app.api.orchestrator import process_signal
import app.core.config as config

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """Verify HMAC-SHA256 signature of the raw request body."""
    webhook_secret = config.WEBHOOK_SECRET
    if not webhook_secret or not webhook_secret.strip():
        return False
    if not signature:
        return False
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/m8")
async def receive_m8_payload(request: Request):
    body = await request.body()
    signature = request.headers.get("x-m8-signature")

    if not _verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid or missing webhook signature")

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    try:
        payload = M8Payload(**data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    try:
        result = await process_signal(payload)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("Error processing M8 payload")
        raise HTTPException(status_code=500, detail="Internal server error processing payload")

import logging
from fastapi import APIRouter, HTTPException
from app.schemas.m8_payload import M8Payload
from app.api.orchestrator import process_signal

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/m8")
async def receive_m8_payload(payload: M8Payload):
    try:
        # Await the async process_signal function
        result = await process_signal(payload)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal server error while processing signal.")

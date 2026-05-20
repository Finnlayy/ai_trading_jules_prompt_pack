from fastapi import APIRouter, HTTPException
from app.schemas.m8_payload import M8Payload
from app.api.orchestrator import process_signal

router = APIRouter()

@router.post("/m8")
async def receive_m8_payload(payload: M8Payload):
    try:
        result = process_signal(payload)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

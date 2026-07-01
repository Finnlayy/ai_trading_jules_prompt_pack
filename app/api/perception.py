from fastapi import APIRouter, HTTPException, Query
from app.schemas.perception import PerceptionContext
from app.services.perception_engine import perception_engine

router = APIRouter()

@router.get("/context", response_model=PerceptionContext)
async def get_perception_context(symbol: str = Query(...), timeframe: str = Query("1m")):
    try:
        context = await perception_engine.build_context(symbol, timeframe)
        return context
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=PerceptionContext)
async def analyze_perception(symbol: str, timeframe: str = "1m"):
    try:
        context = await perception_engine.build_context(symbol, timeframe)
        return context
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

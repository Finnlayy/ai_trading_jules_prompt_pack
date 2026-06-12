from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.simulator import OrderbookSnapshot, SimulatedFill
from app.services.orderbook_simulator import orderbook_simulator

router = APIRouter()

class QuoteRequest(BaseModel):
    venue: str
    symbol: str
    direction: str
    size: float

@router.get("/orderbook/{venue}/{symbol}", response_model=OrderbookSnapshot)
async def get_orderbook(venue: str, symbol: str):
    try:
        return await orderbook_simulator.fetch_snapshot(venue, symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quote-fill", response_model=SimulatedFill)
async def quote_fill(req: QuoteRequest):
    try:
        snapshot = await orderbook_simulator.fetch_snapshot(req.venue, req.symbol)
        fill = await orderbook_simulator.simulate_fill(snapshot, req.direction, req.size)
        return fill
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

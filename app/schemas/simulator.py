from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class OrderbookLevel(BaseModel):
    price: float
    quantity: float

class OrderbookSnapshot(BaseModel):
    symbol: str
    venue: str
    timestamp: int
    bids: List[OrderbookLevel]
    asks: List[OrderbookLevel]

class SimulatedFill(BaseModel):
    symbol: str
    requested_size: float
    filled_size: float
    fill_price: float
    slippage_absolute: float
    slippage_pct: float
    simulated_fees: float
    orderbook_impact: float
    partial_fill: bool
    status: str # "FILLED", "PARTIAL", "REJECTED"

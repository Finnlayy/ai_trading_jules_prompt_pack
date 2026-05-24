from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.api.ai_layer import router as ai_layer_router
from app.api.backtest_runner import router as backtest_router
from app.api.endpoints import router as m8_router
from app.api.market_data import router as market_router

app = FastAPI(
    title="Agent-Reflex Hybrid Trader API",
    description="Simulation-first trading API. Open this UI to inspect health, backtest, and M8 webhook routes.",
)

app.include_router(m8_router, prefix="/webhook", tags=["webhook"])
app.include_router(backtest_router, prefix="/backtest", tags=["backtest"])
app.include_router(ai_layer_router, prefix="/ai", tags=["ai-layer"])
app.include_router(market_router, prefix="/market", tags=["market-data"])

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_frontend():
    with open("frontend.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
def health_check():
    return {"status": "ok"}

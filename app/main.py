from fastapi import FastAPI
from app.api.backtest_runner import router as backtest_router
from app.api.endpoints import router as m8_router

app = FastAPI(title="Agent-Reflex Hybrid Trader API")

app.include_router(m8_router, prefix="/webhook", tags=["webhook"])
app.include_router(backtest_router, prefix="/backtest", tags=["backtest"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

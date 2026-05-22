from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.api.backtest_runner import router as backtest_router
from app.api.endpoints import router as m8_router

app = FastAPI(
    title="Agent-Reflex Hybrid Trader API",
    description="Simulation-first trading API. Open this UI to inspect health, backtest, and M8 webhook routes.",
)

app.include_router(m8_router, prefix="/webhook", tags=["webhook"])
app.include_router(backtest_router, prefix="/backtest", tags=["backtest"])

@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/health")
def health_check():
    return {"status": "ok"}

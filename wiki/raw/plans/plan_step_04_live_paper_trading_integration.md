# Schritt 4: Live Paper Trading Integration

## Ziel

Der autonome Loop aus Schritt 3 wird mit einem Live-Paper-Broker verbunden. Das System führt echte Signale auf Bybit Testnet (oder Pionex Paper) aus, trackt Performance in Echtzeit und stellt ein Live-Dashboard für Monitoring bereit. Alle Sicherheitsgarantien (kein AI-Direct-Live, deterministic gates, circuit breakers) bleiben bestehen.

---

## Scope

| In-Scope | Out-of-Scope |
|----------|--------------|
| Bybit Testnet Paper Broker (vorhanden, aber ausbauen) | Echte Live-Trading mit Echtgeld |
| Live-Fill-Tracking + Position-Monitoring | Cross-Margin / Isolierte-Margin-Logik |
| Realtime-Dashboard-Updates (SSE/WS) | Mobile App |
| Performance-Metriken (Sharpe, Winrate, PnL) | Steuer-Reporting |
| Automatic Shutdown bei Drawdown-Limits | Portfolio-Rebalancing |

---

## Architektur & Datenfluss

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        LIVE PAPER TRADING PIPELINE                       │
│                                                                          │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Autonomous Loop │───▶│ process_signal  │───▶│ PaperBroker         │  │
│  │ (Schritt 3)     │    │ (bestehend)     │    │ (Bybit Testnet)     │  │
│  └─────────────────┘    └─────────────────┘    └──────────┬──────────┘  │
│                                                           │              │
│                              ┌────────────────────────────┘              │
│                              ▼                                           │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Journal Logger  │◄───│ Fill Tracker    │◄───│ Bybit Testnet API   │  │
│  │ (append-only)   │    │ (realtime)      │    │ (REST + optional WS)│  │
│  └─────────────────┘    └────────┬────────┘    └─────────────────────┘  │
│                                  │                                       │
│                                  ▼                                       │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Performance     │◄───│ Position Ledger │◄───│ Dashboard SSE       │  │
│  │ Calculator      │    │ (live state)    │    │ (Frontend updates)  │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Neue Dateien

### 1. `app/services/live_fill_tracker.py`
**Typ:** Service (State Management)
**Agent-Zuweisung:** Backend-Dev / Broker-Integration-Agent

Enthält:
- `LiveFillTracker` — Singleton, trackt offene Positionen in Echtzeit
- Methoden:
  - `record_intent(payload: M8Payload, decision: DecisionEnum)` — Speichert Trade-Intent vor Execution
  - `record_fill(trade_id: str, fill_data: FillData)` — Aktualisiert nach Broker-Confirmation
  - `record_exit(trade_id: str, exit_price: float, exit_time: datetime)` — Schließt Position
  - `get_open_positions() -> list[OpenPosition]`
  - `get_position(trade_id: str) -> OpenPosition | None`
  - `get_daily_pnl() -> float`
  - `sync_with_broker(broker: BaseBroker)` — Abgleich mit Broker-API

**Datenmodelle:**
```python
@dataclass
class FillData:
    entry_price: float
    fill_time: datetime
    size: float
    side: str
    fees: float
    slippage: float

@dataclass
class OpenPosition:
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    realized_pnl: float
    open_time: datetime
    strategy_id: str | None
    stop_price: float
    target_price: float
```

### 2. `app/services/performance_calculator.py`
**Typ:** Service (Analytics)
**Agent-Zuweisung:** Quant-Agent / Backend-Dev

Enthält:
- `PerformanceCalculator` — berechnet Metriken aus Journal + Live-Fills
- Methoden:
  - `calculate_metrics(lookback_days: int = 30) -> PerformanceMetrics`
  - `calculate_sharpe(returns: list[float], risk_free_rate: float = 0.0) -> float`
  - `calculate_sortino(returns: list[float]) -> float`
  - `calculate_max_drawdown(equity_curve: list[float]) -> tuple[float, int, int]`
  - `calculate_winrate(trades: list[TradeJournalEntry]) -> float`
  - `calculate_profit_factor(trades: list[TradeJournalEntry]) -> float`
  - `calculate_expectancy(trades: list[TradeJournalEntry]) -> float`

**PerformanceMetrics:**
```python
@dataclass
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    winrate_pct: float
    profit_factor: float
    expectancy: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    max_drawdown_start_idx: int
    max_drawdown_end_idx: int
    total_pnl: float
    avg_trade_pnl: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    avg_holding_time_minutes: float
    calculated_at: datetime
```

### 3. `app/services/dashboard_sse.py`
**Typ:** Service (Realtime)
**Agent-Zuweisung:** Backend-Dev / Frontend-Agent

Enthält:
- `DashboardSSEManager` — verwaltet Server-Sent Events (SSE) Streams
- Methoden:
  - `connect(client_id: str) -> AsyncGenerator[str, None]`
  - `disconnect(client_id: str)`
  - `broadcast(data: dict)` — Sendet JSON an alle verbundenen Clients
  - `broadcast_trade_update(entry: TradeJournalEntry)`
  - `broadcast_position_update(positions: list[OpenPosition])`
  - `broadcast_metrics_update(metrics: PerformanceMetrics)`
- Hintergrund-Task: Pusht alle 5s Position-Updates, bei Trades sofort

### 4. `app/api/live_trading.py`
**Typ:** API Router
**Agent-Zuweisung:** Backend-Dev

Endpunkte:
- `GET /live/status` — Live-Trading-Status (aktiv/inaktiv, Broker-Mode, Loop-Status)
- `GET /live/positions` — Offene Positionen (aus LiveFillTracker)
- `GET /live/positions/{trade_id}` — Einzelposition
- `POST /live/positions/{trade_id}/close` — Manuelles Schließen einer Position
- `GET /live/performance` — Performance-Metriken (versch. Lookback-Perioden)
- `GET /live/equity-curve?days=30` — Equity-Curve-Daten für Charting
- `GET /live/trades?limit=50&offset=0` — Letzte abgeschlossene Trades
- `GET /live/stream` — SSE-Endpoint für Realtime-Updates
- `POST /live/emergency-stop` — Sofortiger Halt aller neuen Entries, Schließen offener Positionen

### 5. `app/schemas/live_trading.py`
**Typ:** Schema (Pydantic v2)
**Agent-Zuweisung:** Backend-Dev

```python
class LiveTradingStatus(BaseModel):
    is_active: bool
    broker_mode: str
    loop_running: bool
    open_positions_count: int
    total_exposure_usdt: float
    today_pnl: float
    today_trades: int
    circuit_breaker_tripped: bool
    last_trade_at: datetime | None
    uptime_seconds: float

class PositionResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    open_time: datetime
    strategy_id: str | None
    stop_price: float
    target_price: float
    time_in_trade_minutes: float

class PerformanceResponse(BaseModel):
    metrics: PerformanceMetrics
    lookback_days: int
    generated_at: datetime

class EmergencyStopRequest(BaseModel):
    reason: str = "Manual emergency stop"
    close_open_positions: bool = True
    halt_duration_minutes: int = Field(default=60, ge=1, le=1440)

class SSEEvent(BaseModel):
    event_type: Literal["trade", "position", "metrics", "alert", "heartbeat"]
    payload: dict[str, Any]
    timestamp: datetime
```

### 6. `app/scripts/live_paper_smoke.py`
**Typ:** Standalone-Script
**Agent-Zuweisung:** DevOps-Agent

- Führt 5 Papier-Trades auf Bybit Testnet durch
- Prüft Journal-Einträge, Position-Tracking, Performance-Metriken
- Exit-Code 0 bei Erfolg, 1 bei Fehler
- Für CI/CD-Smoke-Tests gedacht

### 7. `tests/services/test_live_fill_tracker.py`
**Agent-Zuweisung:** QA-Agent

Testfälle:
- `test_record_intent_creates_pending_position`
- `test_record_fill_updates_position`
- `test_record_exit_calculates_realized_pnl`
- `test_sync_with_broker_detects_divergence`
- `test_daily_pnl_calculation`

### 8. `tests/services/test_performance_calculator.py`
**Agent-Zuweisung:** QA-Agent

Testfälle:
- `test_sharpe_ratio_positive_returns`
- `test_max_drawdown_identifies_correct_range`
- `test_winrate_calculation`
- `test_profit_factor_greater_than_one_for_profitable`
- `test_expectancy_positive_for_edge`

---

## Änderungen an bestehendem Code

### `app/services/paper_broker.py`
```python
class PaperBroker(BaseBroker):
    # NEU: Echte Bybit Testnet-Integration (bestehend, aber ausbauen)
    def execute_trade(self, payload, decision, ...):
        # Bestehende Simulation-Logik beibehalten als Fallback
        # NEU: Wenn PAPER_BROKER_USE_TESTNET=true:
        #   - Platziere reale Order auf Bybit Testnet
        #   - Warte auf Fill-Confirmation
        #   - Rufe LiveFillTracker.record_fill() auf
        pass

    # NEU: Position-Sync
    async def sync_positions(self) -> list[dict]:
        # Ruft Bybit Testnet /v5/position/list auf
        # Aktualisiert LiveFillTracker
        pass
```

### `app/services/broker_factory.py`
```python
class BrokerFactory:
    @staticmethod
    def create(mode, journal_path, **kwargs):
        # NEU: paper_broker bekommt live_fill_tracker_instance injiziert
        if mode == "paper":
            from app.services.live_fill_tracker import live_fill_tracker_instance
            return PaperBroker(
                journal_path=journal_path,
                fill_tracker=live_fill_tracker_instance,
                **kwargs
            )
```

### `app/api/orchestrator.py`
```python
async def process_signal(payload: M8Payload):
    # ... bestehende Pipeline ...

    # NEU: Live-Fill-Tracking vor Execution
    from app.services.live_fill_tracker import live_fill_tracker_instance
    live_fill_tracker_instance.record_intent(payload, decision_result["decision"])

    # Bestehende Broker-Execution
    journal_entry = broker_instance.execute_trade(...)

    # NEU: Post-Execution Fill-Tracking
    if journal_entry.simulated_fill:
        live_fill_tracker_instance.record_fill(
            journal_entry.trade_id,
            FillData(
                entry_price=journal_entry.simulated_fill.get("fill_price", payload.entry_price),
                fill_time=datetime.now(timezone.utc),
                size=journal_entry.simulated_fill.get("size", 0.0),
                side=payload.direction,
                fees=journal_entry.simulated_fill.get("fees", 0.0),
                slippage=journal_entry.simulated_fill.get("slippage", 0.0),
            )
        )

    # ... restliche Logik ...
```

### `app/main.py`
```python
from app.api.live_trading import router as live_trading_router
app.include_router(live_trading_router, prefix="/live", tags=["live_trading"])

# NEU: SSE-Endpoint registrieren
@app.get("/live/stream")
async def live_stream(request: Request):
    from app.services.dashboard_sse import dashboard_sse_manager
    client_id = str(uuid.uuid4())
    async def event_generator():
        try:
            async for event in dashboard_sse_manager.connect(client_id):
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            dashboard_sse_manager.disconnect(client_id)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# NEU: Periodische Sync-Task für Paper-Broker
async def broker_sync_task():
    while True:
        try:
            if BROKER_MODE == "paper":
                broker = broker_instance
                if hasattr(broker, "sync_positions"):
                    await broker.sync_positions()
        except Exception as e:
            logger.warning(f"Broker sync failed: {e}")
        await asyncio.sleep(30.0)

@app.on_event("startup")
async def startup_event():
    # ... bestehende Startup ...
    asyncio.create_task(broker_sync_task())
```

### `app/core/config.py`
```python
# NEU: Live Paper Trading Konfiguration
PAPER_BROKER_USE_TESTNET = _as_bool(os.getenv("PAPER_BROKER_USE_TESTNET"), True)
PAPER_BROKER_SYNC_INTERVAL_SECONDS = _as_float(os.getenv("PAPER_BROKER_SYNC_INTERVAL_SECONDS"), 30.0)
PAPER_BROKER_API_KEY = os.getenv("PAPER_BROKER_API_KEY", "")
PAPER_BROKER_API_SECRET = os.getenv("PAPER_BROKER_API_SECRET", "")

# NEU: Dashboard / SSE
DASHBOARD_SSE_ENABLED = _as_bool(os.getenv("DASHBOARD_SSE_ENABLED"), True)
DASHBOARD_SSE_HEARTBEAT_SECONDS = _as_float(os.getenv("DASHBOARD_SSE_HEARTBEAT_SECONDS"), 15.0)
DASHBOARD_POSITION_UPDATE_INTERVAL_SECONDS = _as_float(os.getenv("DASHBOARD_POSITION_UPDATE_INTERVAL_SECONDS"), 5.0)

# NEU: Emergency Stop
EMERGENCY_STOP_AUTO_HALT_DRAWDOWN_PCT = _as_float(os.getenv("EMERGENCY_STOP_AUTO_HALT_DRAWDOWN_PCT"), 10.0)
```

### `app/services/telegram_notifier.py`
```python
# NEU: Live-Trading-spezifische Alerts
class TelegramNotifier:
    async def send_position_update(self, position: OpenPosition):
        # Formatierter Position-Update-Text
        pass

    async def send_performance_summary(self, metrics: PerformanceMetrics):
        # Tägliche Performance-Zusammenfassung
        pass

    async def send_emergency_stop_alert(self, reason: str):
        # Sofort-Alert bei Emergency Stop
        pass
```

---

## Teststrategie

1. **Unit Tests:** Performance-Calculator mit synthetischen Trade-Listen
2. **Integration Tests:** PaperBroker + LiveFillTracker + Journal, kompletter Roundtrip
3. **E2E-Tests:** Starte autonomen Loop in Paper-Mode, warte auf Trades, prüfe SSE-Stream
4. **Smoke-Test:** `python -m app.scripts.live_paper_smoke` muss 5 Trades durchführen
5. **Regression:** Alle bestehenden Broker-Tests müssen in Simulation-Mode identisch bleiben

---

## Abhängigkeiten

- **Benötigt:** Schritt 1 (Strategy Engine) — zwingend
- **Benötigt:** Schritt 2 (News-Aware AI Layer) — empfohlen, aber optional
- **Benötigt:** Schritt 3 (Autonomous Loop) — zwingend, da Loop die Signale liefert
- **Optional:** Bybit Testnet API-Keys für echte Paper-Tests

---

## Akzeptanzkriterien

- [ ] `GET /live/positions` zeigt aktuelle offene Positionen mit unrealized PnL
- [ ] `GET /live/performance` liefert Sharpe, Winrate, Profit Factor, Max Drawdown
- [ ] SSE-Stream `/live/stream` pusht Trade-Updates in Echtzeit (<1s Latenz)
- [ ] `POST /live/emergency-stop` stoppt neue Entries und schließt offene Positionen
- [ ] PaperBroker platziert Orders auf Bybit Testnet (wenn konfiguriert)
- [ ] Performance-Metriken stimmen mit manueller Berechnung überein (±0.1% Toleranz)
- [ ] Telegram sendet Position-Updates und Performance-Zusammenfassungen
- [ ] `python -m app.scripts.live_paper_smoke` läuft erfolgreich durch
- [ ] Alle bestehenden 170+ Tests grün, alle neuen Tests grün

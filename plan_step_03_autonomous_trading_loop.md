# Schritt 3: Autonomer Trading Loop

## Ziel

Das System wechselt vom passiven Webhook-Modell („wartet auf externe Signale“) zu einem autonomen, aktiven Trading-Loop. Ein Hintergrund-Task pollt kontinuierlich Marktdaten, generiert über die Strategy Engine Signale, bewertet diese durch AI + Risk Engine und führt sie ohne manuellen Webhook-Trigger aus.

---

## Scope

| In-Scope | Out-of-Scope |
|----------|--------------|
| Background-Task mit asyncio-Loop | Echte WebSocket-Verbindung zu Bybit (nur REST-Polling) |
| Konfigurierbare Watchlist + Timeframes | Multi-Account-Trading |
| Rate-Limited Polling (respektiert API-Limits) | Order-Management nach Entry (Trailing, TP/SL-Adjust) |
| Strategy-Rotation basierend auf Regime | Cross-Exchange-Arbitrage |
| Circuit-Breaker für Loop selbst (bei Fehler) | |

---

## Architektur & Datenfluss

```
┌──────────────────────────────────────────────────────────────────────┐
│                     AutonomousTradingLoop                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Watchlist    │  │ Polling      │  │ Signal       │               │
│  │ Manager      │→ │ Scheduler    │→ │ Generator    │               │
│  │              │  │ (Rate Limit) │  │ (Strategy)   │               │
│  └──────────────┘  └──────────────┘  └──────┬───────┘               │
│                                             │                        │
│  ┌──────────────┐  ┌──────────────┐        ▼                        │
│  │ Loop Health  │  │ Regime-based │  ┌──────────────┐               │
│  │ Monitor      │  │ Strategy     │  │ process_signal│              │
│  │              │  │ Rotation     │← │ (bestehend)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                             │                        │
│                                             ▼                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Trade Journal (append-only)  ←  Broker-Ergebnis          │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Neue Dateien

### 1. `app/services/autonomous_loop.py`
**Typ:** Service (Background-Task)  
**Agent-Zuweisung:** Backend-Dev / Infrastructure-Agent

Enthält:
- `AutonomousTradingLoop` — asyncio-basiert, graceful shutdown
- Attribute:
  - `watchlist: list[WatchlistItem]` — Symbole + Timeframes + Strategie-Overrides
  - `poll_interval_seconds: float` — Standard 60s
  - `is_running: bool`
  - `last_poll_times: dict[str, datetime]` — Pro-Symbol Rate-Limiting
  - `loop_stats: LoopStats` — Zähler, Fehler, Durchsatz
  - `_task: asyncio.Task | None`
- Methoden:
  - `start()` — Startet den Loop als Background-Task
  - `stop()` — Graceful Shutdown (beendet nach aktuellem Durchlauf)
  - `add_symbol(symbol, timeframes, strategy_id=None)`
  - `remove_symbol(symbol)`
  - `set_poll_interval(seconds)`
  - `get_status() -> LoopStatus`
  - `_run_single_cycle()` — Ein Durchlauf: Watchlist iterieren, Daten holen, Signale generieren, Pipeline ausführen
  - `_should_poll(symbol, timeframe) -> bool` — Rate-Limit-Check
  - `_execute_signal(payload: M8Payload)` — Ruft bestehenden `process_signal()` auf
  - `_check_strategy_rotation(symbol, regime)` — Wechselt Strategie bei Regime-Change

**Rate-Limiting:**
- Bybit REST: 120 req/min für Market Data
- Loop berechnet `min_interval = 60.0 / (120 / watchlist_count)` und skaliert dynamisch
- Exponentieller Backoff bei API-Fehlern (1s → 2s → 4s → max 30s)

**Error-Handling:**
- Nach 5 konsekutiven Fehlern: Loop pausiert für 60s, sendet Telegram-Alert
- Nach 20 Fehlern innerhalb 5 Minuten: Loop stoppt automatisch (Circuit-Breaker)

### 2. `app/services/watchlist_manager.py`
**Typ:** Service (State Management)  
**Agent-Zuweisung:** Backend-Dev

Enthält:
- `WatchlistManager` — verwaltet persistierte Watchlist
- Persistenz: `data/watchlist.json`
- `WatchlistItem` dataclass:
  ```python
  @dataclass
  class WatchlistItem:
      symbol: str
      timeframes: list[str]  # ["1m", "5m", "15m"]
      active: bool = True
      strategy_id: str | None = None  # Override gegenüber Global-Default
      min_confluence: float | None = None
      max_position_size_usdt: float | None = None
      added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  ```
- Methoden:
  - `load() / save()`
  - `add(item) / remove(symbol) / update(symbol, **kwargs)`
  - `get_active() -> list[WatchlistItem]`

### 3. `app/services/loop_health_monitor.py`
**Typ:** Service (Observability)  
**Agent-Zuweisung:** Backend-Dev

Enthält:
- `LoopHealthMonitor` — trackt Loop-Metriken
- `HealthSnapshot`:
  - `status: "healthy" | "degraded" | "halted"`
  - `cycles_completed: int`
  - `signals_generated: int`
  - `trades_executed: int`
  - `errors_last_5min: int`
  - `avg_cycle_time_ms: float`
  - `next_poll: datetime | None`
- Telegram-Integration: Sendet Alert bei Status-Change (healthy → degraded → halted)

### 4. `app/schemas/autonomous_loop.py`
**Typ:** Schema (Pydantic v2)  
**Agent-Zuweisung:** Backend-Dev

```python
class WatchlistItemSchema(BaseModel):
    symbol: str = Field(..., pattern=r"^[A-Z0-9]+$")
    timeframes: list[str] = Field(default=["1m", "5m", "15m"])
    active: bool = True
    strategy_id: str | None = None
    min_confluence: float | None = Field(default=None, ge=0, le=100)
    max_position_size_usdt: float | None = Field(default=None, gt=0)

class LoopStatusResponse(BaseModel):
    is_running: bool
    active_symbols: list[str]
    poll_interval_seconds: float
    loop_stats: dict[str, Any]
    health: HealthSnapshotSchema
    current_strategy_id: str

class LoopControlRequest(BaseModel):
    action: Literal["start", "stop", "pause", "resume"]

class StrategyRotationLog(BaseModel):
    symbol: str
    old_strategy: str
    new_strategy: str
    regime: str
    reason: str
    timestamp: datetime
```

### 5. `app/api/autonomous_loop.py`
**Typ:** API Router  
**Agent-Zuweisung:** Backend-Dev

Endpunkte:
- `GET /loop/status` — Loop-Status + Health + Watchlist
- `POST /loop/control` — Start / Stop / Pause / Resume
- `GET /loop/watchlist` — Aktive Watchlist
- `POST /loop/watchlist` — Symbol hinzufügen
- `DELETE /loop/watchlist/{symbol}` — Symbol entfernen
- `PATCH /loop/watchlist/{symbol}` — Symbol-Eigenschaften ändern
- `GET /loop/stats` — Historische Loop-Statistiken (letzte 24h)
- `GET /loop/rotation-log` — Protokoll der Strategy-Rotations

### 6. `tests/services/test_autonomous_loop.py`
**Agent-Zuweisung:** QA-Agent

Testfälle:
- `test_loop_starts_and_stops_gracefully`
- `test_loop_respects_rate_limits`
- `test_loop_executes_process_signal_on_generated_payload`
- `test_loop_skips_inactive_symbols`
- `test_loop_circuit_breaker_after_repeated_errors`
- `test_watchlist_persistence`
- `test_strategy_rotation_on_regime_change`

---

## Änderungen an bestehendem Code

### `app/main.py`
```python
from app.services.autonomous_loop import autonomous_loop_instance

@app.on_event("startup")
async def startup_event():
    # ... bestehende Startup-Logik ...
    # NEU: Autonomous Loop initialisieren (nicht automatisch starten)
    # Start erst via API oder Env-Var
    if _as_bool(os.getenv("AUTONOMOUS_LOOP_AUTO_START"), False):
        autonomous_loop_instance.start()

@app.on_event("shutdown")
async def shutdown_event():
    # ... bestehende Shutdown-Logik ...
    autonomous_loop_instance.stop()

# NEU: Router
from app.api.autonomous_loop import router as loop_router
app.include_router(loop_router, prefix="/loop", tags=["autonomous_loop"])
```

### `app/core/config.py`
```python
# NEU: Autonomous Loop Konfiguration
AUTONOMOUS_LOOP_ENABLED = _as_bool(os.getenv("AUTONOMOUS_LOOP_ENABLED"), False)
AUTONOMOUS_LOOP_AUTO_START = _as_bool(os.getenv("AUTONOMOUS_LOOP_AUTO_START"), False)
AUTONOMOUS_LOOP_POLL_INTERVAL_SECONDS = _as_float(os.getenv("AUTONOMOUS_LOOP_POLL_INTERVAL_SECONDS"), 60.0)
AUTONOMOUS_LOOP_MAX_ERRORS_5MIN = _as_int(os.getenv("AUTONOMOUS_LOOP_MAX_ERRORS_5MIN"), 20)
AUTONOMOUS_LOOP_PAUSE_ON_ERROR_COUNT = _as_int(os.getenv("AUTONOMOUS_LOOP_PAUSE_ON_ERROR_COUNT"), 5)
AUTONOMOUS_LOOP_ERROR_PAUSE_SECONDS = _as_float(os.getenv("AUTONOMOUS_LOOP_ERROR_PAUSE_SECONDS"), 60.0)
AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED = _as_bool(os.getenv("AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED"), True)
```

### `app/api/orchestrator.py`
```python
# NEU: Exportierte Funktion für Loop
async def execute_autonomous_signal(payload: M8Payload) -> dict:
    """
    Wrapper um process_signal für den autonomen Loop.
    Fügt zusätzliche Logging- und Error-Handling-Schicht hinzu.
    """
    try:
        result = await process_signal(payload)
        # NEU: Loop-Statistik aktualisieren
        autonomous_loop_instance.loop_stats.trades_executed += 1
        return result
    except Exception as e:
        autonomous_loop_instance.loop_stats.errors_last_5min += 1
        raise
```

### `app/services/regime_engine.py`
```python
# NEU: Methode für Strategy-Rotation
class RegimeEngine:
    def recommend_strategy(self, regime: str) -> str | None:
        """
        Empfiehlt eine Strategie-ID basierend auf dem Regime.
        Returns None wenn keine Rotation nötig.
        """
        mapping = {
            "TRENDING_BULL": "pattern_enhanced",  # Patterns funktionieren gut in Trends
            "TRENDING_BEAR": "pattern_enhanced",
            "RANGING": "cisd",  # CISD ist robuster in Ranges
            "HIGH_VOLATILITY": "cisd",  # Weniger Noise-sensitiv
            "LOW_VOLATILITY": "pattern_enhanced",
        }
        return mapping.get(regime)
```

---

## Teststrategie

1. **Unit Tests:** Loop-Logik mit gemocktem `process_signal` und gefälschten Market-Daten
2. **Integration Tests:** Loop-Start via API, Symbol hinzufügen, Loop-Durchlauf abwarten, Journal prüfen
3. **Load Tests:** 10+ Symbole in Watchlist, prüfen dass Rate-Limits eingehalten werden
4. **Regression:** Alle Webhook-Tests müssen weiterhin funktionieren (Loop darf bestehende API nicht beeinflussen)

---

## Abhängigkeiten

- **Benötigt:** Schritt 1 (Strategy Engine) — zwingend für Strategie-Rotation
- **Benötigt:** Schritt 2 (News-Aware AI Layer) — empfohlen, aber optional (Loop läuft auch ohne News)
- **Keine neuen externen Dependencies**

---

## Akzeptanzkriterien

- [ ] `POST /loop/control {action: "start"}` startet den Hintergrund-Task
- [ ] `GET /loop/status` zeigt `is_running: true`, Watchlist, Health
- [ ] Loop generiert Signale für alle aktiven Symbole und führt `process_signal()` aus
- [ ] Loop pausiert 60s nach 5 Fehlern, stoppt nach 20 Fehlern in 5 Minuten
- [ ] Bybit API-Rate-Limits werden nicht überschritten (≤120 req/min)
- [ ] Strategy-Rotation findet statt, wenn Regime sich ändert (wenn aktiviert)
- [ ] Alle bestehenden Webhook-Tests grün, Loop-Tests zusätzlich grün

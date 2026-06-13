# Schritt 1: Strategy Engine + Pattern Recognition

## Ziel

Einführung eines konfigurierbaren, plugin-basierten Strategy Frameworks sowie einer rein NumPy-basierten Chart-Pattern-Erkennung. Das System soll mehrere Strategien gleichzeitig verwalten, zur Laufzeit zwischen ihnen wechseln und klassische Chart-Patterns (H&S, Double Top/Bottom, Flags, Pennants, Triangles, Wedges) als zusätzliche Konfluenz-Inputs für den M8-Pipeline bereitstellen.

---

## Scope

| In-Scope | Out-of-Scope |
|----------|--------------|
| Strategy-Definition als Pydantic-Config | Backtest-Optimierung der Patterns |
| Pattern Recognition mit NumPy (ohne TA-Lib) | ML-basierte Pattern-Erkennung |
| Strategy-Registry + Runtime-Selektor | Autonome Loop (Schritt 3) |
| Integration in `signal_generator.py` | News-Injection (Schritt 2) |
| REST API für Strategy-CRUD + Switching | Live Broker-Execution (Schritt 4) |

---

## Architektur & Datenfluss

```
┌─────────────────────────────────────────────────────────────┐
│  Strategy Registry (Singleton)                              │
│  ├─ strategy_map: dict[str, TradingStrategy]               │
│  ├─ active_strategy_id: str                                │
│  └─ default_strategy: CISDStrategy                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SignalGenerator (erweitert)                                │
│  ├─ Lädt aktive Strategie aus Registry                     │
│  ├─ Strategie liefert Score + Richtung pro Bar             │
│  └─ Fallback auf CISDScorer wenn keine Strategie aktiv     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  PatternRecognitionEngine                                   │
│  ├─ Erkennt Patterns auf historischen Bars                 │
│  ├─ Liefert Pattern-Score (0-100) + Pattern-Typ            │
│  └─ Wird von Strategien optional als Input genutzt         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              M8Payload (erweitert)
              └─ pattern_detected: str | null
              └─ pattern_score: float
              └─ strategy_id: str
```

---

## Neue Dateien

### 1. `app/services/strategy_engine.py`
**Typ:** Service (Business Logic)
**Agent-Zuweisung:** Backend-Dev / Core-Engine-Agent

Enthält:
- `BaseStrategy(ABC)` mit Methoden:
  - `score_bars(bars: list[OHLCV]) -> list[StrategyScore]`
  - `get_metadata() -> StrategyMetadata`
  - `required_timeframes() -> list[str]`
- `CISDStrategy(BaseStrategy)` — Wrapper um bestehenden `CISDScorer`
- `PatternEnhancedStrategy(BaseStrategy)` — Kombiniert CISD + Pattern-Scores gewichtet
- `StrategyRegistry` — Singleton, verwaltet geladene Strategien, Persistenz in `data/strategies.json`
- `StrategyScore` dataclass: `direction`, `confluence_score`, `confidence`, `metadata`

### 2. `app/services/pattern_recognition.py`
**Typ:** Service (Algorithmik)
**Agent-Zuweisung:** Quant/Algorithm-Agent

Enthält:
- `PatternRecognitionEngine` — zustandslose Engine, reine Funktionen
- Erkennungsfunktionen (jede liefert `PatternMatch | None`):
  - `detect_head_and_shoulders(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> PatternMatch`
  - `detect_double_top(closes, highs, lows)`
  - `detect_double_bottom(closes, highs, lows)`
  - `detect_flag(closes, highs, lows, volumes)`
  - `detect_triangle(closes, highs, lows)` — ascending, descending, symmetric
  - `detect_wedge(closes, highs, lows)` — rising, falling
- `PatternMatch` dataclass:
  - `pattern_type: str`
  - `direction: "LONG" | "SHORT" | "NEUTRAL"`
  - `confidence: float` (0.0–1.0)
  - `start_idx: int`
  - `end_idx: int`
  - `neckline: float | None`
- Score-Aggregation: Wenn mehrere Patterns gleichzeitig erkannt werden, gewichteter Durchschnitt

**Algorithmik-Details:**
- H&S: Lokale Extrema via `scipy.signal.argrelextrema` (oder simpler: Sliding Window Min/Max), Symmetrie-Check (linke Schulter ≈ rechte Schulter ± 5%), Neckline-Breakout-Validierung
- Double Top/Bottom: Zwei lokale Maxima/Minima im Abstand von 5–30 Bars, Zwischentief/-hoch als Confirmation
- Flags/Pennants: Starker Trend (5–15 Bars) + Konsolidierung (3–10 Bars) + Breakout in Trendrichtung
- Triangles: Konvergierende Trendlinien (mindestens 2 Berührungen pro Linie), Breakout-Richtung
- Wedges: Divergierende/konvergierende Trendlinien gegen den Trend

### 3. `app/schemas/strategy.py`
**Typ:** Schema (Pydantic v2)
**Agent-Zuweisung:** Backend-Dev

```python
class StrategyConfig(BaseModel):
    strategy_id: str = Field(..., pattern=r"^[a-z0-9_-]+$")
    name: str
    description: str = ""
    strategy_type: Literal["cisd", "pattern_enhanced", "custom"]
    weights: dict[str, float] = Field(default_factory=dict)
    enabled: bool = True
    min_confluence: float = Field(default=6.0, ge=0, le=100)
    timeframes: list[str] = Field(default=["1m"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StrategySwitchRequest(BaseModel):
    strategy_id: str
    force: bool = False  # Überspringt Warnung bei offenen Positionen

class StrategyStatusResponse(BaseModel):
    active_strategy_id: str
    available_strategies: list[StrategyConfig]
    last_switch: datetime | None
    pattern_stats: dict[str, int]  # Zähler pro erkanntem Pattern-Typ
```

### 4. `app/api/strategies.py`
**Typ:** API Router
**Agent-Zuweisung:** Backend-Dev

Endpunkte:
- `GET /strategies` — Liste aller registrierten Strategien
- `GET /strategies/active` — Aktive Strategie + Metadaten
- `POST /strategies/switch` — Strategie-Wechsel (mit `force`-Flag)
- `POST /strategies` — Neue Strategie registrieren
- `DELETE /strategies/{strategy_id}` — Strategie entfernen (nicht erlaubt für `default`)
- `POST /strategies/{strategy_id}/backtest-smoke` — Schneller Smoke-Test der Strategie auf letzten 100 Bars

### 5. `app/api/patterns.py`
**Typ:** API Router
**Agent-Zuweisung:** Backend-Dev

Endpunkte:
- `GET /patterns/scan?symbol=BTCUSDT&timeframe=1h&bars=200` — Scannt historische Daten und liefert erkannte Patterns
- `GET /patterns/stats` — Aggregierte Pattern-Erkennungsstatistik (letzte 24h)

### 6. `tests/services/test_strategy_engine.py`
**Agent-Zuweisung:** QA-Agent

Testfälle:
- `test_strategy_registry_singleton`
- `test_cisd_strategy_scores_bars`
- `test_pattern_enhanced_strategy_combines_scores`
- `test_strategy_switch_persists_to_disk`
- `test_invalid_strategy_id_rejected`

### 7. `tests/services/test_pattern_recognition.py`
**Agent-Zuweisung:** QA-Agent

Testfälle:
- `test_detect_double_top_on_synthetic_data`
- `test_detect_head_and_shoulders`
- `test_no_pattern_on_random_noise`
- `test_flag_detection_on_synthetic_trend`
- `test_pattern_confidence_within_bounds`

---

## Änderungen an bestehendem Code

### `app/services/signal_generator.py`
```python
# NEU: Strategy-Integration
from app.services.strategy_engine import strategy_registry

class SignalGenerator:
    def generate_payloads(self, symbol, timeframe, bars, min_confluence=None):
        # ... bestehender Code bis CISD-Scoring ...

        # NEU: Aktive Strategie laden
        strategy = strategy_registry.get_active_strategy()
        strategy_scores = strategy.score_bars(raw_bars)

        # NEU: Pattern-Erkennung (wenn PatternEnhancedStrategy aktiv)
        pattern_results = []
        if isinstance(strategy, PatternEnhancedStrategy):
            from app.services.pattern_recognition import PatternRecognitionEngine
            engine = PatternRecognitionEngine()
            pattern_results = engine.scan_bars(raw_bars)

        # Payload-Erzeugung mit strategy_id + pattern_info
        for i, (bar, s_score, p_result) in enumerate(zip(raw_bars, strategy_scores, pattern_results)):
            # ... bestehende SL/TP-Logik ...
            payload = M8Payload(
                # ... bestehende Felder ...
                strategy_id=strategy.strategy_id,
                pattern_detected=p_result.pattern_type if p_result else None,
                pattern_score=round(p_result.confidence * 100, 2) if p_result else 0.0,
            )
```

### `app/schemas/m8_payload.py`
```python
class M8Payload(BaseModel):
    # ... bestehende Felder ...
    strategy_id: str | None = Field(default=None, description="ID der auslösenden Strategie")
    pattern_detected: str | None = Field(default=None, description="Erkanntes Chart-Pattern")
    pattern_score: float = Field(default=0.0, ge=0, le=100, description="Pattern-Konfidenz 0-100")
```

### `app/main.py`
```python
# NEU: Router-Registrierung
from app.api.strategies import router as strategies_router
from app.api.patterns import router as patterns_router

app.include_router(strategies_router, prefix="/strategies", tags=["strategies"])
app.include_router(patterns_router, prefix="/patterns", tags=["patterns"])
```

### `app/api/backtest_runner.py`
```python
# NEU: Optionaler strategy_id-Parameter für Backtests
@router.post("/run")
async def run_backtest(
    symbol: str = "HYPEUSDT",
    strategy_id: str | None = None,  # NEU
    bars: int = 500,
    ...
):
    if strategy_id:
        strategy_registry.set_active_strategy(strategy_id)
    # ... restlicher Backtest-Code ...
```

---

## Teststrategie

1. **Unit Tests:** Pattern-Erkennung auf synthetischen Datensätzen (numpy-generierte idealisierte Patterns)
2. **Integration Tests:** Strategy-Switch via API + anschließender Signal-Generator-Aufruf
3. **Regression Tests:** Bestehende Backtest-Smoke-Tests müssen mit `CISDStrategy` identische Ergebnisse liefern

---

## Abhängigkeiten

- Keine externen Dependencies (rein NumPy)
- Schritt 2–4 bauen auf der Strategy Engine auf

---

## Akzeptanzkriterien

- [ ] `GET /strategies` liefert mindestens `default` (CISD) und `pattern_enhanced`
- [ ] `POST /strategies/switch` ändert die aktive Strategie persistenzsicher
- [ ] `GET /patterns/scan?symbol=BTCUSDT&bars=500` liefert ≥0 Patterns mit Typ, Richtung, Confidence
- [ ] Backtest mit `strategy_id=pattern_enhanced` produziert unterschiedliche Signale als `default`
- [ ] Alle neuen Tests grün, alle 170 bestehenden Tests weiterhin grün

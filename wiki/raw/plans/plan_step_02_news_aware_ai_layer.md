# Schritt 2: News-Aware AI Layer

## Ziel

Der News Aggregator wird aktiv in den Trading-Loop eingebunden. Gefetchte News werden:
1. In die Prompts der AI Sentiment Scouts injiziert (kontextuelles News-Awareness)
2. Von einem deterministischen `NewsImpactScorer` bewertet (Symbol-Relevanz, Sentiment-Polarität, Dringlichkeit)
3. Als modulierende Faktoren in die Risk Engine eingespeist (temporäre Threshold-Anpassungen bei Breaking News)

---

## Scope

| In-Scope | Out-of-Scope |
|----------|--------------|
| News-Injektion in Sentiment Scout Prompt | Eigene News-Klassifikation via LLM (nur Scoring) |
| Deterministischer NewsImpactScorer | Echtzeit-News-Streaming (nur Polling-Integration) |
| News-basierte Risk-Engine-Modulation | Fundamental-Analyse (Earnings, Bilanzen) |
| News-Cache + Deduplizierung | Social-Media-Sentiment (Twitter/X) |

---

## Architektur & Datenfluss

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ NewsAggregator  │────▶│ NewsImpactScorer         │────▶│ RiskEngine          │
│ (RSS Polling)   │     │ - Symbol-Relevanz        │     │ - Temp. Thresholds  │
└─────────────────┘     │ - Sentiment-Polarität    │     │ - Breaking-News-Flag│
                        │ - Dringlichkeit          │     └─────────────────────┘
                        └────────────┬─────────────┘
                                     │
                                     ▼
                        ┌──────────────────────────┐
                        │ Sentiment Scout Prompt   │
                        │ "Letzte 5 News: ..."     │
                        └──────────────────────────┘
```

---

## Neue Dateien

### 1. `app/services/news_impact_scorer.py`
**Typ:** Service (deterministisch)  
**Agent-Zuweisung:** Risk-Engine-Agent / Quant-Agent

Enthält:
- `NewsImpactScorer` — zustandslos, thread-safe
- Methoden:
  - `score_items(items: list[NewsItem], symbol: str) -> list[ScoredNewsItem]`
  - `aggregate_impact(scored_items: list[ScoredNewsItem]) -> NewsImpactSummary`
  - `get_risk_adjustments(summary: NewsImpactSummary) -> RiskAdjustments`

**Scoring-Dimensionen:**
- `symbol_relevance` (0.0–1.0): Keyword-Matching (Symbol, Asset-Klasse, Synonyme wie "Bitcoin" für BTC)
- `sentiment_polarity` (-1.0 bis +1.0): Lexikon-basiert (positive Wörter: surge, rally, breakthrough; negative: crash, ban, lawsuit, hack)
- `urgency` (0.0–1.0): Keywords: "breaking", "urgent", "just", "alert", "exclusive" → höhere Dringlichkeit
- `recency_decay` (0.0–1.0): Exponentieller Decay basierend auf Alter der News (Halbwertszeit 2h)

**NewsImpactSummary:**
```python
@dataclass
class NewsImpactSummary:
    symbol: str
    overall_sentiment: float  # -1.0 bis +1.0, gewichteter Durchschnitt
    overall_urgency: float    # 0.0 bis 1.0
    article_count: int
    dominant_topics: list[str]
    risk_adjustments: RiskAdjustments
```

**RiskAdjustments:**
```python
@dataclass
class RiskAdjustments:
    # Additive Anpassungen (können positiv oder negativ sein)
    confluence_offset: float = 0.0   # Erhöht/Reduziert Min-Confluence
    crisis_offset: float = 0.0       # Erhöht/Reduziert Max-Crisis
    spread_multiplier: float = 1.0   # Multipliziert Max-Spread
    cooldown_bars_offset: int = 0    # Erhöht Cooldown bei Unsicherheit
    human_review_required: bool = False  # Bei extremen News
```

**Threshold-Regeln (hardcoded, deterministic):**
- Wenn `overall_urgency > 0.8` UND `abs(overall_sentiment) > 0.6`: `human_review_required = True`
- Wenn `overall_sentiment < -0.5`: `crisis_offset = +10.0`, `confluence_offset = +5.0`
- Wenn `overall_sentiment > 0.5`: `crisis_offset = -5.0` (nur bis Minimum 0)
- Wenn `overall_urgency > 0.7`: `cooldown_bars_offset = +1`
- Wenn Breaking-News zu Regulation/Exchange-Hack: `spread_multiplier = 1.5`

### 2. `app/services/news_sentiment_lexicon.py`
**Typ:** Konfiguration/Daten  
**Agent-Zuweisung:** Risk-Engine-Agent

Enthält:
- `POSITIVE_KEYWORDS: dict[str, float]` — Wort → Gewicht (z.B. "rally": 0.8, "breakthrough": 0.9)
- `NEGATIVE_KEYWORDS: dict[str, float]` — Wort → Gewicht (z.B. "crash": 1.0, "hack": 0.9, "lawsuit": 0.7)
- `URGENCY_KEYWORDS: list[str]` — "breaking", "urgent", "alert", "just in", "exclusive"
- `SYMBOL_SYNONYMS: dict[str, list[str]]` — z.B. `{"BTCUSDT": ["bitcoin", "btc"], "ETHUSDT": ["ethereum", "eth"], "XAUUSDT": ["gold", "xau"]}`

### 3. `app/schemas/news_impact.py`
**Typ:** Schema (Pydantic v2)  
**Agent-Zuweisung:** Backend-Dev

```python
class ScoredNewsItem(BaseModel):
    item: NewsItem
    symbol_relevance: float = Field(..., ge=0, le=1)
    sentiment_polarity: float = Field(..., ge=-1, le=1)
    urgency: float = Field(..., ge=0, le=1)
    recency_score: float = Field(..., ge=0, le=1)
    composite_score: float = Field(..., ge=-1, le=1)

class NewsImpactSummarySchema(BaseModel):
    symbol: str
    overall_sentiment: float
    overall_urgency: float
    article_count: int
    dominant_topics: list[str]
    risk_adjustments: dict[str, Any]
    timestamp: datetime

class NewsImpactRequest(BaseModel):
    symbol: str
    max_age_hours: float = Field(default=24.0, ge=1, le=72)
    min_relevance: float = Field(default=0.3, ge=0, le=1)
```

### 4. `app/api/news_impact.py`
**Typ:** API Router  
**Agent-Zuweisung:** Backend-Dev

Endpunkte:
- `GET /news/impact?symbol=BTCUSDT&max_age_hours=24` — Aktueller News-Impact-Score für ein Symbol
- `GET /news/impact/all` — Impact-Scores für alle überwachten Symbole
- `POST /news/refresh` — Erzwingt sofortiges News-Fetch + Scoring
- `GET /news/scored` — Letzte gescorten News-Items mit Metadaten

### 5. `tests/services/test_news_impact_scorer.py`
**Agent-Zuweisung:** QA-Agent

Testfälle:
- `test_symbol_relevance_btc_matches_bitcoin`
- `test_sentiment_positive_article`
- `test_sentiment_negative_article`
- `test_urgency_breaking_keyword`
- `test_recency_decay_old_article`
- `test_risk_adjustments_negative_sentiment_increases_crisis`
- `test_human_review_required_extreme_conditions`
- `test_composite_score_within_bounds`

---

## Änderungen an bestehendem Code

### `app/services/ai_kimi.py` — Sentiment Scout
```python
async def _run_sentiment_scout(self, payload: M8Payload, symbol_context: str) -> str:
    # NEU: News-Abfrage
    from app.services.news_aggregator import news_aggregator_instance
    from app.services.news_impact_scorer import news_impact_scorer
    
    cached_news = news_aggregator_instance.get_cached()
    scored = news_impact_scorer.score_items(cached_news, payload.symbol)
    # Nur Top-5 relevante News
    relevant = sorted(scored, key=lambda x: x.composite_score, reverse=True)[:5]
    news_block = "\n".join(
        f"- [{n.item.source}] {n.item.title} (Relevanz: {n.symbol_relevance:.2f}, Sentiment: {n.sentiment_polarity:.2f})"
        for n in relevant if n.symbol_relevance >= 0.3
    ) or "No relevant recent news."
    
    system = (
        "You are the Sentiment Scout — a market sentiment analyst.\n"
        "Analyze news flow, social sentiment, and event risk for this signal.\n"
        # ... bestehende Instruktionen ...
    )
    prompt = (
        f"Symbol: {payload.symbol}\n"
        f"Direction: {payload.direction}\n"
        # ... bestehende Felder ...
        f"\nRecent relevant news:\n{news_block}\n"
        "Assess sentiment landscape and event risk."
    )
    return await self._call_llm(prompt, system=system)
```

### `app/services/risk_engine.py`
```python
class RiskEngine:
    def evaluate(self, payload: M8Payload, ai_review: SignalReview) -> dict:
        # NEU: News-basierte Anpassungen laden
        from app.services.news_impact_scorer import news_impact_scorer
        from app.services.news_aggregator import news_aggregator_instance
        
        cached_news = news_aggregator_instance.get_cached()
        scored = news_impact_scorer.score_items(cached_news, payload.symbol)
        summary = news_impact_scorer.aggregate_impact(scored)
        adjustments = summary.risk_adjustments
        
        # NEU: Anpassungen auf Thresholds anwenden
        effective_min_confluence = MIN_CONFLUENCE_SCORE + adjustments.confluence_offset
        effective_max_crisis = MAX_CRISIS_SCORE + adjustments.crisis_offset
        effective_max_spread = MAX_SPREAD * adjustments.spread_multiplier
        effective_cooldown = COOLDOWN_BARS + adjustments.cooldown_bars_offset
        
        # Bestehende Gate-Logik mit angepassten Werten
        if payload.confluence_score < effective_min_confluence:
            raise RiskGateException(f"Confluence {payload.confluence_score} < {effective_min_confluence}", "LOW_CONFIDENCE")
        
        if payload.crisis_score > effective_max_crisis:
            raise RiskGateException(f"Crisis {payload.crisis_score} > {effective_max_crisis}", "HIGH_CRISIS")
        
        if payload.spread > effective_max_spread:
            raise RiskGateException(f"Spread {payload.spread} > {effective_max_spread}", "WIDE_SPREAD")
        
        # NEU: Human Review Enforcement
        if adjustments.human_review_required:
            return {
                "decision": DecisionEnum.HUMAN_REVIEW,
                "reject_reason": "NEWS_IMPACT_MANDATES_HUMAN_REVIEW",
            }
        
        # ... restliche Gate-Logik ...
```

### `app/core/config.py`
```python
# NEU: News-Aware Konfiguration
NEWS_IMPACT_ENABLED = _as_bool(os.getenv("NEWS_IMPACT_ENABLED"), True)
NEWS_IMPACT_MAX_AGE_HOURS = _as_float(os.getenv("NEWS_IMPACT_MAX_AGE_HOURS"), 24.0)
NEWS_IMPACT_MIN_RELEVANCE = _as_float(os.getenv("NEWS_IMPACT_MIN_RELEVANCE"), 0.3)
NEWS_IMPACT_SENTIMENT_THRESHOLD = _as_float(os.getenv("NEWS_IMPACT_SENTIMENT_THRESHOLD"), 0.5)
NEWS_IMPACT_URGENCY_THRESHOLD = _as_float(os.getenv("NEWS_IMPACT_URGENCY_THRESHOLD"), 0.7)
NEWS_POLL_INTERVAL_MINUTES = _as_float(os.getenv("NEWS_POLL_INTERVAL_MINUTES"), 15.0)
```

### `app/main.py`
```python
from app.api.news_impact import router as news_impact_router
app.include_router(news_impact_router, prefix="/news", tags=["news"])

# NEU: Background-Task für periodisches News-Polling
async def news_poll_task():
    from app.services.news_aggregator import news_aggregator_instance
    while True:
        try:
            await news_aggregator_instance.fetch(source="all")
        except Exception as e:
            logger.warning(f"News poll failed: {e}")
        await asyncio.sleep(NEWS_POLL_INTERVAL_MINUTES * 60)

@app.on_event("startup")
async def startup_event():
    # ... bestehende Startup-Logik ...
    asyncio.create_task(news_poll_task())
```

---

## Teststrategie

1. **Unit Tests:** Lexikon-basiertes Scoring auf vordefinierten Artikel-Templates
2. **Integration Tests:** API-Aufruf `/news/impact` nach manuellem Fetch
3. **E2E-Tests:** Webhook-M8-Payload senden, während News-Cache mit negativem Artikel gefüllt ist → Erwartung: höherer Crisis-Threshold
4. **Regression:** Bestehende Risk-Engine-Tests müssen identisch bleiben, wenn News-Cache leer

---

## Abhängigkeiten

- **Benötigt:** Schritt 1 (Strategy Engine) — nicht funktional, aber empfohlen für konsistente Architektur
- **Keine neuen externen Dependencies**

---

## Akzeptanzkriterien

- [ ] `GET /news/impact?symbol=BTCUSDT` liefert `overall_sentiment`, `overall_urgency`, `risk_adjustments`
- [ ] Sentiment Scout Prompt enthält relevante News-Headlines
- [ ] Negative News erhöht effektiven `crisis_offset` um ≥5 Punkte
- [ ] Breaking-News mit hoher Dringlichkeit setzt `human_review_required = True`
- [ ] Leerer News-Cache verändert Risk-Engine-Verhalten nicht (Regression)
- [ ] Alle 170+ Tests grün

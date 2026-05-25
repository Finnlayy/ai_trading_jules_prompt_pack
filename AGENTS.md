# Agent-Reflex Hybrid Trader API

## Project Overview

This is a **simulation-first AI trading ecosystem** built as a Python FastAPI application. It receives trading signals ("M8 payloads") via webhooks, subjects them to an AI review layer, runs them through a deterministic risk engine, and simulates or executes trades through configurable broker adapters. All activity is logged to an append-only JSON Lines journal.

The project was created as the backend implementation of a Jules/Manus multi-agent trading research brief. It supports multiple AI providers (Moonshot/Kimi, OpenAI, Google Gemini), multiple broker modes (simulation, paper, Pionex relay/direct, GLINT/Hyperliquid), and includes a full backtest pipeline that fetches historical data from Bybit and runs it through the same production pipeline.

**Default language**: Code, docstrings, and inline comments are in English. Markdown documentation in the repo root (`README.md`, prompt packs, research briefs) is in German.

---

## Tech Stack

- **Runtime**: Python 3.11+
- **Web framework**: FastAPI
- **Validation**: Pydantic v2
- **Server**: Uvicorn
- **HTTP client**: `httpx` (tests), `requests` (data fetching)
- **AI SDK**: `openai` (used for all providers via OpenAI-compatible endpoints)
- **Testing**: `pytest`, `pytest-asyncio`
- **Environment**: `python-dotenv`
- **Virtual environment**: `.venv/` (managed manually; no `pyproject.toml` or `poetry`)

---

## Project Structure

```
.
├── app/                          # Main Python application
│   ├── main.py                   # FastAPI app factory, router inclusion, heartbeat task
│   ├── api/                      # HTTP route handlers
│   │   ├── endpoints.py          # POST /webhook/m8 — M8 payload receiver with HMAC verification
│   │   ├── orchestrator.py       # process_signal() — 4-step pipeline orchestration
│   │   ├── backtest_runner.py    # /backtest/run, /status, /reset, /smoke
│   │   ├── ai_layer.py           # /ai endpoints for AI layer introspection
│   │   ├── market_data.py        # /market data endpoints
│   │   ├── recommendations.py    # /market recommendations
│   │   ├── confidence_registry.py# /confidence registry endpoints
│   │   ├── circuit_breaker.py    # /circuit breaker endpoints
│   │   ├── reconciliation.py     # /reconcile endpoints
│   │   ├── news.py               # /news aggregation endpoints
│   │   ├── broker.py             # /broker introspection endpoints
│   │   └── paper.py              # /paper trading endpoints
│   ├── core/                     # Core infrastructure
│   │   ├── config.py             # Environment variable loading and typed helpers
│   │   └── exceptions.py         # RiskGateException with reason codes
│   ├── schemas/                  # Pydantic models
│   │   ├── m8_payload.py         # Incoming webhook payload
│   │   ├── ai_review.py          # AI layer output (SignalReview)
│   │   ├── journal.py            # Trade journal entry models
│   │   ├── risk_flags.py         # Risk flag model
│   │   └── ai_layer.py           # AI layer introspection schemas
│   ├── services/                 # Business logic and external integrations
│   │   ├── ai_kimi.py            # KimiSwarmService — 4-scout async AI review swarm
│   │   ├── ai_mock.py            # MockAIReviewLayer — deterministic rule-based AI fallback
│   │   ├── ai_swarm_native.py    # Native swarm logic
│   │   ├── ai_layer_memory.py    # AI behavior profile and memory
│   │   ├── risk_engine.py        # Deterministic risk gate evaluation
│   │   ├── war_room_rules.py     # War Room order-management gating
│   │   ├── broker_factory.py     # BrokerFactory — creates broker by mode
│   │   ├── broker_interface.py   # BaseBroker ABC
│   │   ├── broker.py             # SimulationBroker — mock fills with slippage/fees
│   │   ├── paper_broker.py       # PaperBroker — Bybit testnet paper trading
│   │   ├── pionex_relay_broker.py# Pionex relay broker (local webhook forwarding)
│   │   ├── pionex_direct_broker.py# Pionex direct REST API broker
│   │   ├── pionex_api.py         # Pionex REST client and signature logic
│   │   ├── pionex_kelly_sizer.py # Kelly criterion position sizing
│   │   ├── pionex_position_ledger.py# Local position ledger for Pionex direct
│   │   ├── glint_broker.py       # GLINT (Hyperliquid via Telegram bot) broker
│   │   ├── bybit_api.py          # Bybit API helpers
│   │   ├── journal_logger.py     # Append-only JSON Lines writer with rotation
│   │   ├── signal_generator.py   # BybitDataFeed + CISD scoring → M8Payloads
│   │   ├── cisd_scorer.py        # CISD (Confluence Indicator Signal Detector) scoring
│   │   ├── asset_calibrator.py   # Per-asset calibration parameters
│   │   ├── regime_engine.py      # Market regime detection
│   │   ├── portfolio_circuit_breaker.py# Portfolio-level drawdown circuit breaker
│   │   ├── correlation_risk.py   # Cross-position correlation risk limits
│   │   ├── confidence_registry.py# Per-symbol scout accuracy tracking
│   │   ├── statistical_battery.py# Statistical validation tests
│   │   ├── telegram_notifier.py  # Telegram notifications (heartbeat, alerts)
│   │   ├── telegram_advisors.py  # External Telegram advisor hub
│   │   ├── telegram_news_receiver.py# Telegram news ingestion
│   │   ├── news_aggregator.py    # News aggregation service
│   │   ├── json_utils.py         # JSON serialization helpers
│   │   └── ... (additional specialized modules)
│   ├── research/                 # Offline research and data tools
│   │   ├── binance_futures_data.py# Binance USD-M futures kline downloader
│   │   ├── mtf_cisd.py           # Multi-timeframe CISD analysis
│   │   └── reference_corpus.py   # Research source curation documentation
│   └── scripts/                  # Standalone research/backtest scripts
│       ├── backtest_btc_15m.py
│       ├── ga_optimize_hype.py   # Genetic algorithm optimization
│       ├── generate_ga_pines.py  # Generate Pine Script from GA results
│       ├── hypeusdt_1m_backtest_v23.py
│       └── ...
├── tests/                        # pytest suite
│   ├── conftest.py               # Global test fixtures and environment overrides
│   ├── api/                      # API/integration tests
│   ├── services/                 # Service unit tests
│   ├── schemas/                  # Schema validation tests
│   └── research/                 # Research module tests
├── frontend.html                 # React-based standalone dashboard (served at `/`)
├── requirements.txt              # Direct dependencies (no lockfile)
├── .env.example                  # Full environment variable template
├── .env                          # Local secrets (gitignored)
└── run_qa.sh                     # QA script: cleans temp files and runs pytest
```

---

## Build and Run Commands

### Setup

```bash
# Create and activate virtual environment (Windows Git Bash)
python -m venv .venv
source .venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your actual API keys
```

### Run Development Server

```bash
source .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```

### Health Check

```bash
curl http://localhost:8000/health
```

### Send Test M8 Payload

```bash
curl -X POST http://localhost:8000/webhook/m8 \
  -H "Content-Type: application/json" \
  -d '{
    "signal_id": "test-001",
    "symbol": "BTCUSDT",
    "timeframe": "1H",
    "direction": "LONG",
    "timestamp": "2026-05-20T12:00:00Z",
    "entry_price": 100000,
    "stop_price": 99000,
    "target_price": 102000,
    "confluence_score": 85,
    "crisis_score": 10,
    "mc_dispersion": 2,
    "spread": 5
  }'
```

### Run Backtest

```bash
# Via API
POST /backtest/run?symbol=HYPEUSDT&bars=500&max_signals=5&min_confluence=6

# Or offline data download with MTF/CISD report
python -m app.research.binance_futures_data \
  --symbol ETHUSDT \
  --interval 5m \
  --bars 1000 \
  --out app/scripts/data_cache/ETHUSDT_5m_research.csv \
  --mtf-report app/scripts/optimizer_results/ETHUSDT_5m_mtf_cisd.json \
  --mtf-timeframes 15,60,240
```

### Testing

```bash
# Run full test suite
python -m pytest tests/

# Or via QA script
bash run_qa.sh
```

---

## Code Style Guidelines

- **Type hints**: Use Python 3.11+ type hints everywhere (`str | None`, `list[str]`, etc.).
- **Docstrings**: Module-level and public class/method docstrings in English. Google-style or plain descriptive style.
- **Imports**: Group as (1) stdlib, (2) third-party, (3) local `app.*` modules. Use `from __future__ import annotations` where needed.
- **Pydantic**: All inbound/outbound data uses Pydantic v2 `BaseModel` with `Field` constraints. Keep schemas strict.
- **Enums**: Use `str, Enum` for categorical fields (direction, decision, final decision).
- **Constants**: Risk thresholds and configurable defaults live in `app/core/config.py`, loaded from environment variables with typed helpers (`_as_bool`, `_as_float`, `_as_int`, `_as_csv_list`).
- **Line length**: Follow existing patterns (~100-120 chars is acceptable).
- **File encoding**: UTF-8.

---

## Testing Instructions

- **Framework**: `pytest` + `pytest-asyncio`.
- **Test layout**: Tests mirror the `app/` structure: `tests/api/`, `tests/services/`, `tests/schemas/`, `tests/research/`.
- **Global fixtures**: `tests/conftest.py` forces deterministic environment variables:
  - `AI_PROVIDER=moonshot`
  - `BROKER_MODE=simulation`
  - `PIONEX_RELAY_ENABLED=false`
  - `PIONEX_DIRECT_ENABLED=false`
  - `PIONEX_DIRECT_LIVE_TRADING_ENABLED=false`
  - `AI_FAILURE_POLICY=reject_live`
- **State reset**: Use the `reset_state` fixture (or equivalent) to reset `risk_engine_instance`, `journal_logger_instance`, and broker state between tests.
- **Mocking AI**: Tests that exercise the full pipeline mock `ai_review_instance._call_llm` with `AsyncMock` to avoid external API calls.
- **Async tests**: Use `@pytest.mark.asyncio` and `AsyncClient(transport=ASGITransport(app=app), ...)` for FastAPI integration tests.
- **Journal isolation**: Redirect `journal_logger_instance.filepath` to a `tmp_path` fixture in tests to avoid polluting the real `trade_journal.jsonl`.

---

## Security Considerations

### Hard Rule: No AI Direct Live Orders

AI agents are strictly advisory. They may research, classify, hypothesize, backtest, analyze journals, mark risks, and suggest code. Deterministic systems must make the final decision, validate, simulate, reject, log, and execute.

### Live-Safety Defaults

- **All live brokers default to dry-run** unless explicitly enabled:
  - `PIONEX_DIRECT_LIVE_TRADING_ENABLED=false`
  - `PIONEX_RELAY_ENABLED=false`
  - `GLINT_LIVE_TRADING_ENABLED=false`
- `.env` is in `.gitignore`. Never commit API keys, secrets, or wallet private keys.
- `AI_FAILURE_POLICY=reject_live` blocks live-capable orders when the AI layer is unavailable.

### Webhook Authentication

- `POST /webhook/m8` supports optional HMAC-SHA256 signature verification via `x-m8-signature` header and `WEBHOOK_SECRET` env var.
- If `WEBHOOK_SECRET` is empty, verification is skipped for backward compatibility.

### Symbol Validation

- Pionex Direct broker enforces `PIONEX_ALLOWED_SYMBOLS` before accepting any order.
- TradingView perp symbols like `XAGUSDT.P` are normalized to `XAG_USDT_PERP` for Pionex direct mode.

### Order Size Guards

- Direct brokers enforce min/max order size limits (`PIONEX_DIRECT_MIN_ORDER_USDT`, `PIONEX_DIRECT_MAX_ORDER_USDT`, etc.).

---

## Architecture and Data Flow

### Main Pipeline

```
M8 Webhook → Regime Check → AI Review → Risk Engine → Broker → Journal Logger
```

1. **POST /webhook/m8** receives and validates `M8Payload` (Pydantic + HMAC).
2. **Regime Check** (`orchestrator._check_regime`) fetches recent Bybit bars and evaluates market regime. Fails open if data is unavailable.
3. **AI Review** (`ai_kimi.KimiSwarmService.review_signal`) runs 4 scouts concurrently (Technical, Sentiment, Risk, Macro) plus optional external Telegram advisors. Returns a `SignalReview`.
4. **Risk Engine** (`risk_engine.RiskEngine.evaluate`) applies deterministic gates in order:
   - Explicit M8 reject
   - War Room order classification (`GO`/`HOLD`/`KILL`)
   - Minimum confluence score (default 70)
   - Maximum crisis score (default 30)
   - Maximum MC dispersion (default 5)
   - Maximum spread (default 15)
   - Minimum R:R ratio (default 2.0)
   - Cooldown bars (default 3)
   - Max trades per day (default 5)
   - Portfolio circuit breaker (drawdown halt)
   - Correlation risk limit
   - AI conflict (if AI rejected or requires human review)
5. **Broker** (`BrokerFactory.create`) executes or simulates based on `BROKER_MODE`.
6. **Journal Logger** appends `TradeJournalEntry` to `trade_journal.jsonl` (append-only NDJSON with rotation).

### Broker Modes

| Mode | Class | Live Capable | Description |
|------|-------|-------------|-------------|
| `simulation` | `SimulationBroker` | No | Mock fills with static slippage (2 bps) + fees (5 bps). Trades stay `OPEN`. |
| `paper` | `PaperBroker` | No | Bybit testnet paper trading. |
| `pionex_relay` | `PionexRelayBroker` | Yes (gated) | Forwards to local Pionex relay server at `PIONEX_RELAY_URL`. |
| `pionex_direct` | `PionexDirectBroker` | Yes (gated) | Native Pionex REST API with Kelly sizing, position ledger, and reconciliation. |
| `glint` | `GlintBroker` | Yes (gated) | Hyperliquid perps via Telegram bot integration. |

### AI Provider Selection

Set `AI_PROVIDER` in `.env`:
- `moonshot` → Moonshot/Kimi (`kimi-k2.6`)
- `openai` → OpenAI (`gpt-5.2`)
- `gemini` → Google Gemini (`gemini-2.5-pro`)
- `mock` → `MockAIReviewLayer` (no external API calls)

All providers use the `openai` Python client with provider-specific `base_url` and `api_key`.

### War Room Order Management

The deterministic "War Room" layer adds order-level controls beyond the risk engine:
- `order_command`: `GO`, `HOLD`, `KILL`
- `market_regime`: `GREEN`, `YELLOW`, `ORANGE`, `RED`
- `bar_confirmed`: must be `true` for new entries
- `chop_index`: above threshold triggers standby
- `hurst_exponent` + `macro_event_risk`: trigger orange risk caps
- `drawdown_pct`: hard kill above `WAR_ROOM_HARD_KILL_DRAWDOWN_PCT`
- `pending_order_age_seconds`: expired pending orders are blocked
- VIP thresholds: higher confluence, lower crisis/MC dispersion for premium signals

---

## Configuration Reference

Key environment variables (see `.env.example` for the complete list):

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `moonshot` | AI provider for review swarm |
| `BROKER_MODE` | `simulation` | Active broker mode |
| `PIONEX_RELAY_ENABLED` | `false` | Enable relay forwarding |
| `PIONEX_DIRECT_ENABLED` | `false` | Enable direct Pionex API |
| `PIONEX_DIRECT_LIVE_TRADING_ENABLED` | `false` | **Critical**: set `true` for real orders |
| `GLINT_ENABLED` | `false` | Enable GLINT broker |
| `GLINT_LIVE_TRADING_ENABLED` | `false` | **Critical**: set `true` for real GLINT orders |
| `AI_FAILURE_POLICY` | `reject_live` | Block live if AI unavailable |
| `WEBHOOK_SECRET` | `""` | HMAC secret for webhook verification |
| `TELEGRAM_NOTIFICATIONS_ENABLED` | `false` | Telegram heartbeat/alerts |
| `KELLY_DEPLOY_MODE` | `half` | `half`, `full`, or `fixed` Kelly sizing |
| `WAR_ROOM_ENABLED` | `true` | Enable War Room order gates |
| `SIGNAL_MIN_CONFLUENCE_OVERRIDE` | `None` | Lower backtest threshold (does not affect live risk engine) |

---

## Development Conventions

- **Broker implementations**: Must inherit from `BaseBroker` (`app/services/broker_interface.py`) and implement `execute_trade`, `get_positions`, `get_wallet_balances`, `is_live_capable`, `is_ready`.
- **Risk gates**: Use `RiskGateException(message, reason_code)` for short-circuiting. Each gate must have a unique `reason_code` string.
- **Journal format**: `trade_journal.jsonl` is append-only NDJSON. Never overwrite; always append. Rotation is size-based (10 MB default).
- **State management**: `RiskEngine` holds mutable state (`trades_today`, `last_trade_bar`, `current_bar`). Be cautious with thread safety if scaling beyond a single instance.
- **Research separation**: `app/research/` modules are for offline experimentation. The live broker pipeline must not import research modules that perform network I/O or file writes.
- **Scout accuracy tracking**: `ConfidenceRegistry` tracks per-symbol, per-scout accuracy and weights future syntheses accordingly.
- **Telegram advisors**: Optional external advisors (GLINT, Manus) are queried asynchronously with timeouts. Their responses are advisory only and must not override deterministic gates.

---

## Deployment Notes

- No containerization (Dockerfile, docker-compose) is present in the repo.
- The intended deployment is direct Uvicorn execution:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- The app includes a background heartbeat task that sends Telegram status updates every hour.
- The standalone `frontend.html` is served at `/` and provides a React-based dashboard that communicates with the local API.

---

## Useful Files for Agents

- `app/core/config.py` — canonical list of all environment variables and typed loaders.
- `app/services/broker_factory.py` — how broker modes map to classes.
- `app/schemas/m8_payload.py` — exact fields and validation rules for incoming signals.
- `app/services/risk_engine.py` — all deterministic risk gates and their order.
- `tests/conftest.py` — test environment overrides that must be respected.
- `.env.example` — complete reference for every configurable parameter.

# Agent Operating Instructions

## Role
You are the Lead Security Architect and Responsible Disclosure Orchestrator for this repository.
Work defense-first: validate findings, patch root causes, avoid overclaiming, and keep dangerous proof-of-concepts defanged.

## Project Overview

This is an **AI-assisted trading control system** built in Python, not a generic dashboard.
The target direction is a **Pionex-first autonomous trading bot** with a Kimi/K2.6-style swarm AI layer and a web UI as the operator surface.

- **Runtime**: Python 3.14 (observed in `app/.venv`), compatible with Python 3.11+
- **Web framework**: FastAPI + Uvicorn
- **Validation**: Pydantic v2
- **Persistence**: SQLAlchemy ORM with SQLite by default (`app/data/trading.db`)
- **Journal**: Append-only NDJSON file (`trade_journal.jsonl`)
- **Frontend**: Single static HTML file (`frontend.html`) served at `GET /`
- **Package management**: Plain `pip` + `requirements.txt` (no `pyproject.toml`, `setup.py`, or `package.json`)

Do not restart the project from scratch. Patch the existing architecture step by step and keep the system moving back toward the intended trading-bot design.

## Technology Stack & Runtime Architecture

- **ASGI server**: Uvicorn (`uvicorn app.main:app --reload --port 8000`)
- **ORM / DB**: SQLAlchemy 2.x-style declarative base, repository pattern in `app/db/repository.py`
- **Background tasks**: Asyncio loops started in `app/main.py` startup event:
  - Telegram heartbeat (hourly)
  - News RSS polling (interval from `NEWS_POLL_INTERVAL_MINUTES`)
  - Price poller for live position monitoring (`app/services/price_poller.py`)
  - Autonomous trading loop auto-start (optional, `AUTONOMOUS_LOOP_AUTO_START`)
- **Broker adapters** (factory in `app/services/broker_factory.py`):
  - `simulation` — `SimulationBroker` (default, static slippage/fees, no real orders)
  - `paper` — `PaperBroker` (Bybit testnet)
  - `pionex_relay` — `PionexRelayBroker` (local webhook relay)
  - `pionex_direct` — `PionexDirectBroker` (native REST, dry-run unless explicitly enabled)
  - `glint` — `GlintBroker` (Hyperliquid perps via Telegram bot)
  - `ctrader` — `CTraderBroker` (cTrader Open API)
- **AI layer**:
  - Provider-configurable: Moonshot/Kimi, OpenAI, Google Gemini, or `mock`
  - Per-scout providers: `AI_PROVIDER_TECHNICAL`, `SENTIMENT`, `RISK`, `MACRO`, `EXECUTION`, `CORRELATION`
  - Deterministic fallback: `MockAIReviewLayer` when `AI_PROVIDER=mock`

## Project Structure

```text
.
├── app/                          # Main Python application package
│   ├── main.py                   # FastAPI app factory, router inclusion, startup/shutdown events
│   ├── api/                      # FastAPI routers (webhooks, backtest, broker, market data, etc.)
│   │   ├── endpoints.py          # POST /webhook/m8 — M8 payload entry point
│   │   ├── orchestrator.py       # process_signal() — 4-step pipeline orchestration
│   │   ├── backtest_runner.py    # Backtest execution endpoints
│   │   ├── broker.py             # Broker status and control endpoints
│   │   ├── live_trading.py       # Live trading & position endpoints
│   │   ├── autonomous_loop.py    # Autonomous loop control
│   │   ├── ai_layer.py           # AI swarm endpoints
│   │   ├── market_data.py        # OHLCV / indicator endpoints
│   │   ├── news.py               # News & sentiment endpoints
│   │   ├── strategies.py         # Strategy registry endpoints
│   │   ├── patterns.py           # Pattern recognition endpoints
│   │   ├── confidence_registry.py
│   │   ├── circuit_breaker.py
│   │   ├── reconciliation.py
│   │   ├── paper.py
│   │   ├── news_impact.py
│   │   ├── db_insight.py
│   │   └── ctrader.py
│   ├── core/
│   │   ├── config.py             # All environment-based configuration with typed helpers
│   │   └── exceptions.py         # RiskGateException with reason_code
│   ├── db/
│   │   ├── __init__.py           # SQLAlchemy engine, SessionLocal, Base, get_db()
│   │   ├── models.py             # ORM models: Trade, Position, PerformanceSnapshot, StrategyRotation, NewsImpact
│   │   └── repository.py         # Repository classes for CRUD and analytics
│   ├── schemas/                  # Pydantic v2 models
│   │   ├── m8_payload.py         # Incoming webhook payload
│   │   ├── ai_review.py          # AI layer output
│   │   ├── journal.py            # Trade journal enums and models
│   │   ├── risk_flags.py
│   │   ├── strategy.py
│   │   ├── live_trading.py
│   │   ├── news_impact.py
│   │   ├── autonomous_loop.py
│   │   ├── ctrader.py
│   │   ├── academy.py
│   │   └── m8_payload.py
│   ├── services/                 # Business logic
│   │   ├── broker_factory.py     # BrokerFactory — single-mode broker selection
│   │   ├── broker.py             # SimulationBroker
│   │   ├── broker_interface.py   # BaseBroker ABC
│   │   ├── risk_engine.py        # Deterministic gating logic
│   │   ├── strategy_engine.py    # Pluggable strategy framework with registry
│   │   ├── signal_generator.py   # Bybit data feed and signal generation
│   │   ├── pattern_recognition.py
│   │   ├── portfolio_circuit_breaker.py
│   │   ├── position_monitor.py
│   │   ├── price_poller.py
│   │   ├── autonomous_loop.py
│   │   ├── ai_kimi.py            # AI swarm orchestrator
│   │   ├── ai_mock.py            # Mock AI review layer
│   │   ├── ai_swarm_native.py
│   │   ├── ai_layer_memory.py
│   │   ├── pionex_api.py
│   │   ├── pionex_direct_broker.py
│   │   ├── pionex_relay_broker.py
│   │   ├── pionex_kelly_sizer.py
│   │   ├── pionex_position_ledger.py
│   │   ├── ctrader_broker.py
│   │   ├── glint_broker.py
│   │   ├── paper_broker.py
│   │   ├── news_aggregator.py
│   │   ├── news_impact_scorer.py
│   │   ├── war_room_rules.py
│   │   ├── correlation_risk.py
│   │   ├── cisd_scorer.py
│   │   ├── regime_engine.py
│   │   ├── journal_logger.py
│   │   ├── confidence_registry.py
│   │   ├── agent_registry.py
│   │   ├── prompt_evolution.py
│   │   ├── training_drills.py
│   │   ├── academy_curriculum.py
│   │   └── ...
│   ├── research/                 # Offline research layer
│   │   ├── binance_futures_data.py
│   │   ├── mtf_cisd.py
│   │   └── reference_corpus.py
│   ├── scripts/                  # Standalone scripts
│   │   ├── backtest_btc_15m.py
│   │   ├── ga_optimize_hype.py
│   │   ├── generate_ga_pines.py
│   │   └── ...
│   ├── data/
│   │   ├── strategies.json
│   │   └── trading.db            # SQLite database (created at startup)
│   └── ai_prompts/               # Markdown prompt templates per scout
│       ├── technical/
│       ├── sentiment/
│       ├── risk/
│       ├── macro/
│       ├── execution/
│       └── correlation/
├── tests/                        # pytest suite
│   ├── conftest.py               # Forces safe env defaults for determinism
│   ├── api/
│   ├── db/
│   ├── research/
│   ├── schemas/
│   └── services/
├── data/                         # JSON runtime data (watchlists, registries, positions)
├── logs/                         # JSON runtime logs
├── frontend.html                 # Operator UI (MetricFlow Bot Command Center)
├── requirements.txt              # Dependencies
├── .env.example                  # Full configuration template
└── run_qa.sh                     # Quick test runner (pytest)
```

## Key Data Flows

### 1. M8 Webhook Pipeline
```
POST /webhook/m8
  → HMAC-SHA256 verification (optional, via WEBHOOK_SECRET)
  → M8Payload validation (Pydantic)
  → process_signal() in api/orchestrator.py
    1. AI Review (ai_kimi / ai_mock) → SignalReview
    2. RiskEngine.evaluate() → deterministic gates
    3. Broker execution (factory-selected broker)
    4. JournalLogger → SQL + trade_journal.jsonl
```

### 2. Deterministic War Room Order Management
The Risk Engine and War Room rules enforce hard gates **before** any broker execution:
- `order_command`: `GO`, `HOLD`, `KILL`
- `bar_confirmed` must be `true` for new entries
- `chop_index` above `WAR_ROOM_CHOP_STANDBY_THRESHOLD` → standby
- `drawdown_pct` above `WAR_ROOM_HARD_KILL_DRAWDOWN_PCT` → hard block
- `hurst_exponent` / `macro_event_risk` → orange risk cap
- AI confidence below `WAR_ROOM_AI_MIN_CONFIDENCE` blocks live entry paths
- `CLOSE` orders remain prioritized over entry blocks

### 3. Autonomous Loop
If enabled, `app/services/autonomous_loop.py` polls signals, runs the same pipeline, and can auto-rotate strategies based on regime detection.

## Build & Run Commands

No compilation or Docker build is required.

```bash
# 1. Create / activate virtual environment (Windows Git Bash observed)
python -m venv app/.venv
source app/.venv/Scripts/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — keep PIONEX_DIRECT_LIVE_TRADING_ENABLED=false unless explicitly authorized

# 4. Run development server
uvicorn app.main:app --reload --port 8000

# 5. Health check
curl http://localhost:8000/health
```

The server creates SQLAlchemy tables automatically at startup (`Base.metadata.create_all`).

## Test Commands & Strategy

```bash
# Run the full suite
python -m pytest tests/

# Run a specific service test
python -m pytest tests/services/test_risk_engine.py -v

# Quick QA wrapper (also exists as run_qa.sh)
python -m pytest tests/
```

- **Determinism**: `tests/conftest.py` pins `AI_PROVIDER=moonshot`, `BROKER_MODE=simulation`, disables all Pionex/relay/live flags, and sets `AI_FAILURE_POLICY=reject_live` before any test imports run.
- **Singletons**: Many services expose module-level singleton instances (e.g., `risk_engine_instance`, `circuit_breaker_instance`). Tests use fixtures to reset shared state (e.g., `circuit_breaker_instance.reset()`).
- **Async**: `pytest-asyncio` is available for async test cases.
- **Offline research tests**: `tests/research/` validate Binance data fetching, MTF/CISD scoring, and reference corpus integrity. These do not hit live broker APIs.

## Code Style Guidelines

- **Python version**: Use 3.11+ syntax (`str | None`, etc.). Observed runtime is 3.14.4.
- **Annotations**: Most modules include `from __future__ import annotations`.
- **Imports order**: stdlib → third-party → `app.*` internal modules.
- **Schemas**: All API payloads are Pydantic `BaseModel` with `Field` constraints and regex patterns where applicable.
- **DB layer**: SQLAlchemy declarative models in `app/db/models.py`, CRUD in `app/db/repository.py`, sessions via `app/db/get_db()`.
- **Configuration**: Centralized in `app/core/config.py`, read from `.env` via `python-dotenv`. Use typed helpers (`_as_bool`, `_as_float`, `_as_csv_list`) rather than raw `os.getenv` elsewhere.
- **Exceptions**: Use `RiskGateException(message, reason_code)` for deterministic gate rejections.
- **Broker pattern**: `BaseBroker` ABC → concrete brokers → `BrokerFactory.create(mode)`.
- **Logging**: Trade journal is append-only NDJSON. Do not overwrite `trade_journal.jsonl`; append only.

## Configuration & Environment

Key environment variables (see `.env.example` for the complete list):

| Variable | Typical Value | Purpose |
|----------|---------------|---------|
| `BROKER_MODE` | `simulation` | Broker adapter selection |
| `AI_PROVIDER` | `moonshot` | Default AI provider |
| `AI_PROVIDER_RISK` | `openai` | Per-scout overrides |
| `PIONEX_DIRECT_ENABLED` | `false` | Enable Pionex REST adapter |
| `PIONEX_DIRECT_LIVE_TRADING_ENABLED` | `false` | **Hard safety switch for real orders** |
| `WAR_ROOM_ENABLED` | `true` | Deterministic order-management override |
| `WEBHOOK_SECRET` | `""` | HMAC verification for M8 webhooks |
| `DATABASE_URL` | `sqlite:///app/data/trading.db` | SQLAlchemy DB URL |

**Paper trading should use live market/broker context where safe**, including Pionex wallet/position/status reads, but paper mode must not place real Pionex orders unless live trading is explicitly enabled by a separate human-approved change. Treat Pionex dry-run/paper trading as local virtual execution plus read-only live context, not as exchange-side paper execution.

## Security And Safety Rules

- Only analyze or change code, configs, architectures, or domains explicitly provided or authorized by the user.
- If a request implies third-party or live infrastructure outside the authorized project scope, stop and ask for scope clarification.
- Never label a vulnerability confirmed unless there is a logical source-to-sink path.
- Classify uncertain issues as `Confirmed Finding`, `Theoretical Weakness`, or `Needs More Evidence`.
- Remediation is the primary deliverable; prefer root-cause fixes over payload blocks.
- Proofs of concept must be harmless and must not include persistence, exfiltration, lateral movement, destructive automation, or offensive tradecraft.
- Completed security assessments must remain paused drafts pending human review.

## Trading Bot Guardrails

- Live execution must remain disabled unless a specific human-reviewed patch enables it.
- AI may influence review confidence, reasons, and paper-learning decisions, but deterministic live risk gates remain authoritative.
- Paper/shadow simulations may admit live-rejected candidates for learning, but must record both the strict live decision and the paper decision.
- Outcome learning means persistent confidence/profile/prompt-context learning, not model weight training.
- Keep audit traces explicit enough to understand agent votes, risk gates, paper decisions, and simulated outcomes.

## Work Style

- Make one coherent patch at a time. Avoid attempting the entire roadmap in one pass.
- Before a large patch, inspect the relevant code paths and keep the change narrowly scoped.
- After each large patch, run targeted tests and create a Git commit. Push to GitHub when credentials/remotes are available and the user has not asked to hold back.
- Do not overwrite or revert unrelated user changes in a dirty worktree.
- Preserve current modules and contracts unless a small interface addition is needed to complete the step.

## Reporting

For security findings, include severity, CVSS v3.1 vector, status, affected component, impact, validation path, reproduction logic, remediation, patch candidate, and assumptions.

For implementation work, final responses should state:
- what changed,
- what was tested,
- what remains next,
- and whether a commit/push was created.

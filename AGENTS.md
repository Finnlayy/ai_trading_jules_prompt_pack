<!-- AGENTS.md — Operating instructions for AI coding agents working on this repository. -->

# Agent Operating Instructions

## Role

You are an AI software engineering agent working on this repository. Operate defense-first: validate assumptions, patch root causes, avoid overclaiming, and keep dangerous proof-of-concepts defanged. When you encounter security concerns, classify them precisely and prefer root-cause fixes over surface-level blocks.

The repository is **actively developed** on the `main` branch. Make one coherent patch at a time, run targeted tests, and preserve existing contracts unless a small interface addition is strictly required.

## Project Overview

This is an **AI-assisted trading control system** built in Python. It is **not** a generic dashboard. The target direction is a **Pionex-first autonomous trading bot** with a Kimi/K2.6-style swarm AI layer and a web UI as the operator surface. Over time the architecture has expanded to support multiple broker adapters (Kraken, cTrader, GLINT/Hyperliquid), a full paper-trading simulation layer, an Academy self-improvement layer with an optional PPO meta-policy, and a GEM-10 native AI review pipeline.

- **Runtime**: Python 3.11+ (3.12 observed in Cursor Cloud; a Windows dev machine with 3.14 has also been used)
- **Web framework**: FastAPI + Uvicorn
- **Validation**: Pydantic v2
- **Persistence**: SQLAlchemy ORM. The default `DATABASE_URL` is **PostgreSQL** (`postgresql://postgres:postgres@localhost:5432/metricflow`, assembled from `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`). SQLite is fully supported by setting `DATABASE_URL=sqlite:///app/data/trading.db` and is the practical choice for local dev and CI (no Postgres required).
- **Journal**: Append-only NDJSON file (`trade_journal.jsonl`), rotated at 10 MB (`.1`, `.2`, ... suffixes), mirrored into the SQL `Trade` table, and triggering `wiki_service.update_second_brain()` on writes.
- **Frontend (production)**: Vite + React + TypeScript SPA in `frontend/` (`frontend/src/*.tsx`). The **prebuilt bundle `frontend/dist/` is committed** and mounted at `GET /` by `app/main.py`. Rebuild with Vite only when changing `frontend/src` (there is no `package.json` in the repo — it is gitignored — so recreate Node tooling locally if you must rebuild).
- **Frontend (legacy)**: `frontend.html` at the repo root is the older standalone React app (React/ReactDOM/Babel/Lightweight Charts loaded from `app/static/vendor/`, served under `/static`). It is **not** served at `/` anymore, but `tests/ui/test_frontend_button_contracts.py` and `tests/api/test_frontend_api_contract.py` still parse it as a contract file.
- **Auth**: Google Sign-In → backend-issued JWT (`app/api/auth.py`). Most API routers are protected with `Depends(get_current_user)` (Bearer JWT). `GET /health` requires an `X-API-Key` header matching the `API_KEY` (or `WEBHOOK_SECRET`) env var. Webhook endpoints require **mandatory** HMAC-SHA256 signatures (`x-m8-signature` on `/webhook/m8`, `X-Signature` on `/api/webhook/signal`) computed with `WEBHOOK_SECRET` (dev default `test_secret`; a config warning message still claims unsigned requests are accepted — that is stale, they are rejected).
- **E2E Testing**: Playwright via the `pytest-playwright` plugin (no root `package.json`; install with `pip install pytest-playwright && playwright install chromium`)
- **Package management**: plain `pip` + `requirements.txt` (no `pyproject.toml` or `setup.py`). `requirements-rl.txt` is a **separate, optional** stack (torch/gymnasium/stable-baselines3/onnx) for Academy PPO training; install it only into a dedicated Python 3.11 venv (`.venv-rl`), never into the main venv.

**Context for non-code files**: The repository root also contains a German-language "Jules Prompt Pack" (`01_jules_masterprompt.md`, `02_research_brief_input.md`, `README.md`, etc.). These are planning documents and do **not** affect the runtime code. `README.md` describes the prompt pack, not the runtime. The Python codebase, comments, and docstrings are entirely in English.

Both `.Jules/` and `.jules/` exist at the repository root. They contain a lightweight learning journal (`bolt.md`, `palette.md`, plus `submit.md` / `pre_commit.md` in `.jules/`) recording past performance optimizations and frontend overhaul lessons. Consult them before repeating expensive mistakes.

Do not restart the project from scratch. Patch the existing architecture step by step and keep the system moving back toward the intended trading-bot design.

## Technology Stack & Runtime Architecture

- **ASGI server**: Uvicorn (`uvicorn app.main:app --reload --port 8000`)
- **ORM / DB**: SQLAlchemy 2.x-style declarative base, repository pattern in `app/db/repository.py`
- **Background tasks**: Asyncio loops started in `app/main.py` startup event:
 - Telegram heartbeat (hourly)
 - News RSS polling (interval from `NEWS_POLL_INTERVAL_MINUTES`)
 - Price poller for live position monitoring (`app/services/price_poller.py`)
 - Autonomous trading loop auto-start (optional, `AUTONOMOUS_LOOP_AUTO_START`)
 - Training loop auto-start (optional, `TRAINING_LOOP_AUTO_START`)
 - Shadow queue processor for rejected-trade feedback (every 5 minutes)
 - Webhook consumer for autonomous signal → paper order execution
 - Position monitor for auto stop-loss / take-profit
- **Broker adapters** (factory in `app/services/broker_factory.py`; aliases in parentheses):
 - `simulation` (`sim`) — `SimulationBroker` (default, static slippage/fees, no real orders)
 - `orderbook_sim` — order-book-aware simulator (`app/services/orderbook_simulator.py`)
 - `paper` — `PaperBroker` (Bybit testnet)
 - `pionex_relay` (`relay`) — `PionexRelayBroker` (local webhook relay)
 - `pionex_direct` (`pionex`, `direct`, `pionex_api`) — `PionexDirectBroker` (native REST, dry-run unless explicitly enabled)
 - `glint` — `GlintBroker` (Hyperliquid perps via Telegram bot)
 - `ctrader` (`ctrader_direct`) — `CTraderBroker` (cTrader Open API)
 - `ctrader_fix` — `CTraderFixBroker` (cTrader FIX API)
 - `kraken` — `KrakenBroker` (spot REST API)
 - `kraken_paper` (`krakenpaper`) — `KrakenPaperBroker` (paper trades against live Kraken public prices, persisted to SQL: `PaperTrade`, `PaperPosition`, `PaperBalance`)
- **AI layer**:
 - Engine selection via `AI_REVIEW_ENGINE` in `app/services/ai_factory.py`:
   - `gem10_native` (default) — GEM-10 agent pipeline in `app/services/ai/` (`gem_native_review.py`, `gem_agents.py`, `gem_pipeline.py`)
   - `legacy6` — six-scout swarm orchestrator in `app/services/ai_kimi.py` (tests pin this engine)
 - Provider-configurable: Moonshot/Kimi, OpenAI, Google Gemini, LM Studio (local), or `mock`
 - Per-scout providers: `AI_PROVIDER_TECHNICAL`, `AI_PROVIDER_SENTIMENT`, `AI_PROVIDER_RISK`, `AI_PROVIDER_MACRO`, `AI_PROVIDER_EXECUTION`, `AI_PROVIDER_CORRELATION`
 - Deterministic fallback: `MockAIReviewLayer` when `AI_PROVIDER=mock`
- **Research / offline layer** (`app/research/`):
 - Binance futures data downloader
 - MTF/CISD scoring framework
 - Reference corpus curator
- **Academy / self-improvement layer**:
 - `app/services/training_loop.py`, `training_drills.py`, `academy_curriculum.py`, `agent_registry.py`
 - `app/services/academy_policy/` — PPO/heuristic meta-policy that plans drill cycles (`ACADEMY_POLICY_MODE=shadow|ppo`, `ACADEMY_POLICY_BACKEND=heuristic|onnx`), with ONNX runtime + backtesting subpackage (`app/services/academy_policy/backtesting/`)
 - RL training scripts: `app/scripts/train_academy_ppo.py`, `export_academy_policy_onnx.py`, `academy_rl_runtime.py` (require the separate `.venv-rl`)
 - `app/services/prompt_evolution.py` — prompt A/B testing and mutation tracking
 - `app/services/confidence_registry.py` — per-scout, per-symbol accuracy tracking
- **Gem tool bridge (repo root)**:
 - `tool_interface_gateway.py` — allowlisted JSON dispatcher between external Gems/LLMs and the FastAPI backend
 - `risk_gate_validator.py` — deterministic preflight risk-gate validator for Gem/LLM signal handoff

## Project Structure

```text
.
├── app/ # Main Python application package
│ ├── main.py # FastAPI app factory, router inclusion (JWT-protected), startup/shutdown events, SPA mount
│ ├── api/ # FastAPI routers
│ │ ├── auth.py # POST /api/auth/google — Google token → JWT; get_current_user; get_api_key
│ │ ├── endpoints.py # POST /webhook/m8 — M8 payload entry point
│ │ ├── webhook_signal.py # POST /api/webhook/signal — external signal queue with HMAC
│ │ ├── orchestrator.py # process_signal() — 4-step pipeline orchestration
│ │ ├── backtest_runner.py # Backtest execution endpoints
│ │ ├── broker.py # Broker status and control endpoints
│ │ ├── live_trading.py # Live trading & position endpoints
│ │ ├── autonomous_loop.py # Autonomous loop control
│ │ ├── ai_layer.py # AI swarm endpoints
│ │ ├── market_data.py # OHLCV / indicator endpoints
│ │ ├── news.py / news_impact.py
│ │ ├── strategies.py # Strategy registry endpoints
│ │ ├── patterns.py # Pattern recognition endpoints
│ │ ├── academy.py # Training academy + ONNX policy endpoints (prefix /academy)
│ │ ├── agentic.py # LangGraph agentic reasoning runs
│ │ ├── lifecycle.py # Paper-training lifecycle control
│ │ ├── perception.py # Perception engine endpoints
│ │ ├── recommendations.py # Market recommendations
│ │ ├── simulator.py # Order-book simulator endpoints
│ │ ├── confidence_registry.py, circuit_breaker.py, reconciliation.py
│ │ ├── paper.py, db_insight.py, ctrader.py, ctrader_fix.py
│ │ ├── kraken.py (prefix /kraken), kraken_paper.py (prefix /kraken/paper)
│ │ └── ...
│ ├── core/
│ │ ├── config.py # All environment-based configuration with typed helpers
│ │ ├── exceptions.py # RiskGateException with reason_code
│ │ └── utils.py # strip_html, iso_from_pubdate, json_dumps, async file writers
│ ├── db/
│ │ ├── __init__.py # SQLAlchemy engine (Postgres default, SQLite supported), SessionLocal, Base, get_db()
│ │ ├── models.py # ORM models: Trade, Position, PaperTrade, PaperPosition, PaperBalance,
│ │ │ # PerformanceSnapshot, StrategyRotation, NewsImpact, SignalCandidate,
│ │ │ # AgentReviewEvent, RiskDecisionEvent, PaperOutcome, AgentLearningEvent, AgenticRun
│ │ └── repository.py # Repository classes for CRUD and analytics
│ ├── schemas/ # Pydantic v2 models (m8_payload, ai_review, journal, webhook_signal,
│ │ # risk_flags, strategy, live_trading, news_impact, autonomous_loop,
│ │ # ctrader, kraken, academy, gem_pipeline, lifecycle, paper, perception,
│ │ # risk_result, simulator, trading_plan, ...)
│ ├── services/ # Business logic (single-file services + subpackages)
│ │ ├── broker_factory.py # BrokerFactory — single-mode broker selection (see mode list above)
│ │ ├── broker_interface.py # BaseBroker ABC; broker.py = SimulationBroker
│ │ ├── kraken_broker.py, kraken_paper_broker.py, ctrader_broker.py, ctrader_fix_broker.py
│ │ ├── pionex_api.py, pionex_direct_broker.py, pionex_relay_broker.py
│ │ ├── pionex_kelly_sizer.py, pionex_position_ledger.py, glint_broker.py, paper_broker.py
│ │ ├── risk_engine.py # Deterministic gating logic (imports polars)
│ │ ├── strategy_engine.py, signal_generator.py, pattern_recognition.py
│ │ ├── portfolio_circuit_breaker.py, position_monitor.py, price_poller.py
│ │ ├── autonomous_loop.py, webhook_consumer.py, shadow_queue.py, shadow_paper_engine.py
│ │ ├── ai_factory.py # AI engine selection (gem10_native | legacy6 | mock)
│ │ ├── ai/ # GEM-10 native review pipeline
│ │ ├── ai_kimi.py, ai_mock.py, ai_swarm_native.py, ai_layer_memory.py
│ │ ├── academy_policy/ # PPO/heuristic meta-policy + ONNX runtime + backtesting/tests
│ │ ├── training_loop.py, training_drills.py, academy_curriculum.py, agent_registry.py
│ │ ├── agentic_reasoning.py # LangGraph StateGraph reasoning (imports langgraph)
│ │ ├── paper_training_engine.py, paper_training_pipeline.py, lifecycle_recorder.py
│ │ ├── perception_engine.py, orderbook_simulator.py, smart_order_router.py
│ │ ├── news_aggregator.py, news_impact_scorer.py, news_sentiment_lexicon.py
│ │ ├── war_room_rules.py, correlation_risk.py, cisd_scorer.py, regime_engine.py
│ │ ├── statistical_battery.py, delta_analyzer.py, journal_logger.py
│ │ ├── confidence_registry.py, prompt_evolution.py, prompt_rag.py, ab_testing.py
│ │ ├── watchlist_manager.py, loop_health_monitor.py, dashboard_sse.py, wiki_service.py
│ │ └── ...
│ ├── research/ # Offline research layer
│ ├── scripts/ # Standalone scripts (backtests, GA optimizers, PPO training/export,
│ │ # reset_runtime_state.py, quality_check.py, data_cache/, optimizer_results/)
│ ├── data/
│ │ ├── strategies.json
│ │ └── trading.db # SQLite database (only when DATABASE_URL points at it)
│ ├── ai_prompts/ # Markdown prompt templates per scout + gems/ + chat/
│ └── static/
│ └── vendor/ # React, ReactDOM, Babel, Lightweight Charts (for legacy frontend.html)
├── frontend/ # Production Vite + React + TypeScript SPA
│ ├── src/ # App.tsx, components/ (ChartPanel, Login, OrderTable, Ticker, WarRoom), context/
│ ├── dist/ # COMMITTED build output — served at GET /
│ └── vite.config.ts # Dev proxy → localhost:8000
├── tests/ # pytest suite
│ ├── conftest.py # Forces safe env defaults for determinism
│ ├── api/ # Router/API tests (largest API suite)
│ ├── core/ # config helper tests
│ ├── db/
│ ├── e2e/ # Playwright E2E tests (conftest strips asyncio markers)
│ ├── integration/
│ ├── research/
│ ├── schemas/
│ ├── scripts/
│ ├── services/ # Largest suite
│ ├── ui/ # Frontend button-contract tests (parse legacy frontend.html)
│ ├── test_main.py
│ ├── tdd_architectural_audit.py
│ └── tdd_autonomous_queue.py
├── data/ # JSON runtime data (watchlists, registries, positions, shadow queue)
│ # NOTE: tracked in git but mutated by test runs — do not commit incidental churn
├── wiki/ # Operator knowledge base ("second brain") updated by wiki_service
├── logs/ # JSON runtime logs (gitignored)
├── .Jules/ + .jules/ # AI agent learning journals (bolt.md, palette.md, ...)
├── frontend.html # LEGACY operator UI (kept for UI contract tests; not served at /)
├── tool_interface_gateway.py # Gem → FastAPI JSON dispatcher (repo root)
├── risk_gate_validator.py # Deterministic preflight validator (repo root)
├── requirements.txt # Python dependencies (main venv)
├── requirements-rl.txt # Optional PPO/ONNX stack for a separate Python 3.11 .venv-rl
├── .env.example # Configuration template (not exhaustive — see app/core/config.py)
└── run_qa.sh # Quick test runner (backend + Playwright E2E)
```

## Key Data Flows

### 1. M8 Webhook Pipeline
```
POST /webhook/m8
 → HMAC-SHA256 verification (required; x-m8-signature header, keyed by WEBHOOK_SECRET)
 → M8Payload validation (Pydantic)
 → process_signal() in api/orchestrator.py
 1. AI Review (ai_factory → gem10_native or legacy6, or mock) → SignalReview
 2. RiskEngine.evaluate() → deterministic gates
 3. Broker execution (factory-selected broker)
 4. JournalLogger → SQL + trade_journal.jsonl (rotated at 10 MB)
```

### 2. External Signal → Paper Trading Pipeline
```
POST /api/webhook/signal
 → HMAC-SHA256 verification (required; X-Signature header, keyed by WEBHOOK_SECRET)
 → WebhookSignalPayload validation
 → Enqueued in signal_queue (asyncio.Queue)
 → WebhookConsumer dequeues and executes via KrakenPaperBroker
 → PaperTrade / PaperPosition / PaperBalance updated in SQL
```

### 3. Deterministic War Room Order Management
The Risk Engine and War Room rules enforce hard gates **before** any broker execution:
- `order_command`: `GO`, `HOLD`, `KILL`
- `bar_confirmed` must be `true` for new entries
- `chop_index` above `WAR_ROOM_CHOP_STANDBY_THRESHOLD` → standby
- `drawdown_pct` above `WAR_ROOM_HARD_KILL_DRAWDOWN_PCT` → hard block
- `hurst_exponent` / `macro_event_risk` → orange risk cap
- AI confidence below `WAR_ROOM_AI_MIN_CONFIDENCE` blocks live entry paths
- `CLOSE` orders remain prioritized over entry blocks

### 4. Shadow Queue Learning Loop
Rejected signals are persisted to `data/shadow_queue.jsonl`. A background task evaluates them after enough bars have elapsed, feeding outcome data back into the confidence registry so scouts learn even from trades that never executed.

### 5. Autonomous Loop
If enabled, `app/services/autonomous_loop.py` polls symbols from the watchlist, generates signals, runs the same pipeline, and can auto-rotate strategies based on regime detection.

### 6. Academy Training Loop
If enabled, `app/services/training_loop.py` runs drill cycles planned by `academy_policy_service.plan_cycle()` — one drill per registered scout in `ACADEMY_POLICY_SCOUT_NAMES` (16 scouts currently; do **not** hardcode 6). Results feed `agent_registry`, `academy_curriculum`, diversity monitoring, and optional auto prompt evolution.

## Build & Run Commands

No compilation or Docker build is required for the backend. The frontend SPA is prebuilt and committed.

```bash
# 1. Create / activate virtual environment (repo root)
python3 -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate

# 2. Install Python dependencies
pip install -r requirements.txt
# For Playwright E2E/UI tests only:
pip install pytest-playwright && playwright install chromium

# 3. Configure environment
cp .env.example .env
# Keep PIONEX_DIRECT_LIVE_TRADING_ENABLED=false unless explicitly authorized.
# Without a local PostgreSQL server, set: DATABASE_URL=sqlite:///app/data/trading.db

# 4. Run development server
DATABASE_URL="sqlite:///app/data/trading.db" API_KEY=dev-local-key \
  uvicorn app.main:app --reload --port 8000

# 5. Health check (X-API-Key required; API_KEY or WEBHOOK_SECRET must be set)
curl -H "X-API-Key: dev-local-key" http://localhost:8000/health

# 6. Open the UI
# GET / serves the Vite SPA (frontend/dist). Most /api routes need a Bearer JWT
# from POST /api/auth/google (requires GOOGLE_CLIENT_ID); webhooks use HMAC instead.
```

The server creates SQLAlchemy tables automatically at startup (`Base.metadata.create_all`).

## Test Commands & Strategy

```bash
# Run the full QA suite (backend + Playwright E2E)
DATABASE_URL="sqlite:///app/data/trading.db" ./run_qa.sh

# Backend tests only (run_qa.sh also includes the academy_policy backtesting tests)
DATABASE_URL="sqlite:///app/data/trading.db" python -m pytest \
  tests/api/ tests/db/ tests/research/ tests/schemas/ tests/services/ \
  app/services/academy_policy/backtesting/tests/ \
  tests/tdd_autonomous_queue.py tests/tdd_architectural_audit.py -v

# E2E Playwright tests only
python -m pytest tests/e2e/ -v --browser chromium

# UI / frontend contract tests (parse legacy frontend.html)
python -m pytest tests/ui/ -v --browser chromium

# Run a specific service test
DATABASE_URL="sqlite:///app/data/trading.db" python -m pytest tests/services/test_risk_engine.py -v
```

**pytest configuration** (`pytest.ini`):
- `asyncio_mode = auto`
- `asyncio_default_fixture_loop_scope = function`
- Default quiet mode (`-q`)

**E2E isolation** (`tests/e2e/conftest.py`): Strips `pytest-asyncio` markers from E2E items to avoid event-loop conflicts with Playwright.

**Determinism**: `tests/conftest.py` pins `AI_PROVIDER=moonshot`, `AI_REVIEW_ENGINE=legacy6`, `BROKER_MODE=simulation`, disables all Pionex/relay/live flags, sets `AI_FAILURE_POLICY=reject_live` and `ACADEMY_POLICY_MODE=shadow` / `ACADEMY_POLICY_BACKEND=heuristic` before any test imports run. It does **not** pin `DATABASE_URL` — export it yourself when no Postgres is available.

**Singletons**: Many services expose module-level singleton instances (e.g., `risk_engine_instance`, `circuit_breaker_instance`, `webhook_consumer_instance`, `training_loop`, `agent_registry`). Tests use fixtures to reset shared state (e.g., `circuit_breaker_instance.reset()`).

**Async**: `pytest-asyncio` is available for async test cases. When mocking async service methods (e.g. `training_drills.write_results`, `evaluate_drill`), use `AsyncMock` — a bare `MagicMock` cannot be awaited.

**Runtime-data churn**: Running the backend suite mutates tracked files under `data/` and `wiki/` (and `app/data/trading.db` when using SQLite). Restore them before committing (`git checkout -- data/ wiki/ app/data/trading.db`) unless a change there is intentional.

**Offline research tests**: `tests/research/` validate Binance data fetching, MTF/CISD scoring, and reference corpus integrity. These do not hit live broker APIs.

## Code Style Guidelines

- **Python version**: Use 3.11+ syntax (`str | None`, etc.).
- **Annotations**: Most modules include `from __future__ import annotations`.
- **Imports order**: stdlib → third-party → `app.*` internal modules.
- **Schemas**: All API payloads are Pydantic `BaseModel` with `Field` constraints and regex patterns where applicable.
- **DB layer**: SQLAlchemy declarative models in `app/db/models.py`, CRUD in `app/db/repository.py`, sessions via `app/db/get_db()`.
- **Configuration**: Centralized in `app/core/config.py`, read from `.env` via `python-dotenv`. Use typed helpers (`_as_bool`, `_as_int`, `_as_float`, `_as_optional_float`, `_as_csv_list`) rather than raw `os.getenv` elsewhere. Note: `config.py` currently contains duplicated blocks from past merges — when editing a setting, search for **all** assignments of that name.
- **Exceptions**: Use `RiskGateException(message, reason_code)` for deterministic gate rejections.
- **Broker pattern**: `BaseBroker` ABC → concrete brokers → `BrokerFactory.create(mode)`.
- **Logging**: Trade journal is append-only NDJSON. Do not overwrite `trade_journal.jsonl`; append only (rotation is handled by `JournalLogger`).
- **Async I/O safety**: When a synchronous function (networking, disk I/O, heavy CPU) is called inside an `async def` route or background loop, wrap it with `await asyncio.to_thread(sync_function, ...)` to avoid blocking the event loop.
- **Merge hygiene**: Several past merges have left interleaved duplicate blocks (double imports, duplicated functions, half-merged bodies). When you touch a file, check for and repair such artifacts in the code you edit; never resolve a conflict by keeping both halves.
- **Frontend**: The production UI lives in `frontend/src` (Vite + React + TS); `frontend/dist` is the committed build output served at `/`. The legacy `frontend.html` has no build step and is loaded by UI contract tests — be extremely careful with regex-based edits there; manual or AST-based approaches are preferred.

## Configuration & Environment

Key environment variables (see `.env.example` and `app/core/config.py` — config.py is the source of truth; `.env.example` is not exhaustive):

| Variable | Typical Value | Purpose |
|----------|---------------|---------|
| `BROKER_MODE` | `simulation` | Broker adapter selection (see full mode list above) |
| `AI_PROVIDER` | `moonshot` | Default AI provider (`moonshot`, `openai`, `gemini`, `lmstudio`, `mock`) |
| `AI_REVIEW_ENGINE` | `gem10_native` | AI review pipeline (`gem10_native` or `legacy6`) |
| `AI_PROVIDER_RISK` | `openai` | Per-scout overrides |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/metricflow` | SQLAlchemy DB URL; use `sqlite:///app/data/trading.db` without Postgres |
| `GOOGLE_CLIENT_ID` | `""` | Google Sign-In client for `/api/auth/google` |
| `JWT_SECRET_KEY` | change in prod | Signs backend JWTs guarding most API routers |
| `API_KEY` | `""` | `X-API-Key` for `GET /health` (falls back to `WEBHOOK_SECRET`) |
| `CORS_ORIGINS` | `*` | CORS allow-list (CSV) |
| `PIONEX_DIRECT_ENABLED` | `false` | Enable Pionex REST adapter |
| `PIONEX_DIRECT_LIVE_TRADING_ENABLED` | `false` | **Hard safety switch for real orders** |
| `WAR_ROOM_ENABLED` | `true` | Deterministic order-management override |
| `WEBHOOK_SECRET` | `test_secret` (dev default) | HMAC key for webhook signatures (mandatory checks; set a strong value for live modes) |
| `NEWS_POLL_INTERVAL_MINUTES` | `15` | RSS news polling interval |
| `AUTONOMOUS_LOOP_ENABLED` | `false` | Enable autonomous trading loop |
| `AUTONOMOUS_LOOP_AUTO_START` | `false` | Auto-start loop on server startup |
| `TRAINING_LOOP_ENABLED` | `true` | Enable AI training academy drills |
| `TRAINING_LOOP_AUTO_START` | `false` | Auto-start training loop on server startup |
| `ACADEMY_POLICY_MODE` | `shadow` | Academy meta-policy mode (`shadow` or `ppo`) |
| `ACADEMY_POLICY_BACKEND` | `heuristic` | Policy backend (`heuristic` or `onnx`) |
| `KRAKEN_ENABLED` | `false` | Enable Kraken spot broker |
| `KRAKEN_LIVE_TRADING_ENABLED` | `false` | Hard safety for Kraken real orders |
| `KRAKEN_DEMO_MODE` | `true` | Kraken demo / sandbox flag |
| `CTRADER_ENABLED` / `CTRADER_FIX_ENABLED` | `false` | Enable cTrader adapters |
| `GLINT_ENABLED` | `false` | Enable GLINT (Hyperliquid via Telegram) |
| `TELEGRAM_NOTIFICATIONS_ENABLED` | `false` | Telegram heartbeat & alerts |

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
- Consult `.Jules/` and `.jules/` (`bolt.md`, `palette.md`) before repeating known performance or frontend mistakes.

## Cursor Cloud specific instructions

- The Python venv lives at the **repo root**: `/workspace/.venv` (not `app/.venv`). Activate with `source .venv/bin/activate`; Python 3.12.
- **No PostgreSQL server runs in the VM.** Always export `DATABASE_URL=sqlite:///app/data/trading.db` (or another SQLite path) before importing the app, starting uvicorn, or running pytest — otherwise startup/tests fail with `psycopg2.OperationalError: Connection refused`.
- `GET /health` requires `X-API-Key`; start the server with `API_KEY=<value>` set and pass the same header in curl checks.
- Playwright + Chromium for `tests/e2e/` and `tests/ui/` come from `pip install pytest-playwright` and `playwright install chromium` (there is no root `package.json`).
- Do not install `requirements-rl.txt` into the main venv; RL/ONNX work needs a separate Python 3.11 `.venv-rl` and is normally out of scope in this VM.
- Backend test runs mutate tracked runtime files (`data/*.json[l]`, `wiki/*.md`, `app/data/trading.db`). Restore them with `git checkout -- data/ wiki/ app/data/trading.db` before committing.

## Reporting

For security findings, include severity, CVSS v3.1 vector, status, affected component, impact, validation path, reproduction logic, remediation, patch candidate, and assumptions.

For implementation work, final responses should state:
- what changed,
- what was tested,
- what remains next,
- and whether a commit/push was created.

## Cursor Cloud specific instructions

Environment is Ubuntu 24.04 with Python 3.12 and Node 22. Dependencies live in a
Python virtualenv at `/workspace/.venv` (the startup/update script creates it and
installs `requirements.txt`). System `python3` is externally managed (PEP 668), so
always run tools via `.venv/bin/...` (e.g. `.venv/bin/python -m pytest ...`,
`.venv/bin/uvicorn app.main:app --reload --port 8000`).

Non-obvious caveats discovered during setup:

- **`.env` is required and gitignored.** Copy from `.env.example`, then set
  `DATABASE_URL=sqlite:///app/data/trading.db`. `.env.example` omits `DATABASE_URL`,
  and `app/core/config.py` otherwise defaults to `postgresql://...@localhost:5432`,
  which makes several modules fail at import/startup (no Postgres in this env). For
  offline dev without AI API keys, set `AI_PROVIDER=mock` (deterministic
  `MockAIReviewLayer`). `.env` persists in the VM snapshot, so it does not need to
  be recreated each run.
- **`requirements.txt` was missing runtime deps** (`sqlalchemy`, `polars`,
  `langgraph`) that the app imports directly; they are now added. If a future run
  starts from a base without that change, the update script also installs them
  explicitly.
- **`GET /health` is shadowed** by the SPA static mount at `/` (route added after
  the `app.mount("/")`), so it returns 404 despite existing. To check liveness, load
  `GET /` (serves the SPA) or hit an API route (e.g. `GET /broker/status` with a
  bearer token).
- **Auth gates almost every API router** via `Depends(get_current_user)` (JWT bearer,
  `app/api/auth.py`). Only `/webhook/*` and `/api/auth/*` are unauthenticated. The
  committed tests in `tests/api/` do NOT send tokens, so ~70 tests currently fail
  with `401` on this branch — this is pre-existing repo state, not an environment
  problem (backend suite is otherwise ~508 passed). Mint a dev JWT with
  `JWT_SECRET_KEY` (default `fallback_secret_key_change_in_production`, HS256) to call
  protected endpoints.
- **The core trading pipeline is testable unauthenticated** via
  `POST /webhook/m8`, but it requires `WEBHOOK_SECRET` set in `.env` plus an
  `x-m8-signature` header = HMAC-SHA256(secret, raw_body). It runs
  AI review -> risk engine -> simulation broker -> journal (`trade_journal.jsonl`).
  The regime pre-check calls Bybit and fails open when egress is blocked.
- **Frontend is now a Vite/React SPA** served from the committed `frontend/dist`
  (the "standalone `frontend.html`" description elsewhere is outdated). There is no
  `frontend/package.json`, so the SPA cannot be rebuilt in-repo; the committed
  `dist` is what the backend serves. Login uses Google OAuth with a placeholder
  client ID, so real login does not work in dev — to view the dashboard, set a valid
  JWT in `localStorage.jwtToken` and reload.
- **Tests**: run the backend suite with `run_qa.sh` or the pytest commands above via
  `.venv/bin/python -m pytest ...`. `tests/e2e/` are deprecated stubs that skip;
  `run_qa.sh` passes `--browser chromium`, which requires `pytest-playwright`
  (installed in the venv). There is no configured linter; `.venv/bin/python -m
  compileall app` is a reasonable syntax check.
- **`app/ai_prompts/*/v_active.md` are dangling symlinks**; `rg`/tools may print
  "No such file or directory" warnings — harmless.
Environment: Ubuntu, Python 3.12, Node 22. The startup update script creates a repo-root
`.venv/` and runs `pip install -r requirements.txt`. Prefix Python commands with `.venv/bin/`
(e.g. `.venv/bin/uvicorn ...`, `.venv/bin/python -m pytest ...`). The venv lives at repo root
`.venv/`, not `app/.venv/` as older docs suggest.

Required `.env` (gitignored; create once with `cp .env.example .env`). Non-obvious gotchas:
- **DB defaults to Postgres, not SQLite.** `app/core/config.py` builds
  `postgresql://postgres:postgres@localhost:5432/metricflow` when `DATABASE_URL` is unset, so a
  bare `.env` makes startup crash with a psycopg2 "connection refused". For local dev with no
  Postgres, set `DATABASE_URL=sqlite:///app/data/trading.db` (matches the documented SQLite
  default). Tables auto-create at startup.
- For fully offline runs set `AI_PROVIDER=mock` and the per-scout `AI_PROVIDER_*=mock`; otherwise
  the swarm needs real Moonshot/OpenAI/Gemini keys.
- Protected endpoints (e.g. `GET /health`) require `API_KEY` (or `WEBHOOK_SECRET`) to be set, else
  they return 500 "Server misconfiguration". Call them with header `X-API-Key: <API_KEY>`.
- `POST /webhook/m8` requires `WEBHOOK_SECRET` set **and** an `x-m8-signature` header =
  HMAC-SHA256(raw_body, WEBHOOK_SECRET). An empty secret rejects every request with 401, despite
  the stale startup warning claiming unauthenticated requests are accepted.

Running: `.venv/bin/uvicorn app.main:app --reload --port 8000` serves both the JSON API and the
operator UI. The UI is a **pre-built Vite SPA** (source in `frontend/`, build output in
`frontend/dist`, mounted at `/`); the old "standalone `frontend.html` via CDN" description is
outdated. Rebuild it with `npm install && npm run build` inside `frontend/`. The login uses Google
Identity Services; the SPA fetches the OAuth client ID **at runtime** from `GET /api/auth/config`
(which returns `GOOGLE_CLIENT_ID`), so you only set `GOOGLE_CLIENT_ID` in `.env` — no rebuild is
needed to change it. Reaching the dashboard still needs a **real** Google OAuth 2.0 Web Client ID
(`...apps.googleusercontent.com`) with `http://localhost:8000` as an authorized origin, plus a real
Google login, so full UI auth against live `/api` data is not exercisable headless. However, the
committed `frontend/dist` SPA renders the full operator dashboard at `/` (chart, War Room consensus,
orders table with demo/placeholder data) without a Google login, so the UI itself **can** be
smoke-tested headlessly by loading `http://localhost:8000/`. A good headless smoke test of core
backend functionality is the signed `POST /webhook/m8` pipeline (AI review → risk engine →
simulation broker → `trade_journal.jsonl`).

External market data (Bybit `api.bybit.com`) returns HTTP 403 from this sandbox. The regime check
degrades gracefully (`trade_allowed=true`, `regime=UNKNOWN`); do not treat Bybit 403 as a setup
failure.

Lint/test/build:
- No linter is configured (no ruff/flake8/black/mypy). The closest "lint" is
  `.venv/bin/python -m compileall app`.
- Backend tests: run the `run_qa.sh` backend subset. Known **pre-existing** breakages unrelated to
  environment setup: `tests/services/test_statistical_battery.py` (syntax error ~line 207) and
  `tests/services/test_news_aggregator.py` (imports functions removed from the module) fail
  collection — exclude them with `--ignore`. A handful of other tests are pre-existing drift/flaky
  (`test_endpoints.py::test_root_serves_frontend` expects the old UI title, `test_training_loop`
  MagicMock misuse, `test_brain_compressor_caching`, `test_agent_registry` file-handle isolation).
  Additionally, tests that hit **live external market data** fail here because egress is blocked
  (`Connection reset by peer` / HTTP 502): the Kraken (`tests/api/test_kraken*.py`,
  `tests/services/test_kraken_paper_broker.py`) and Binance-backed research/backtest tests
  (`tests/research/test_backtest_engine.py`, `test_market_data_loader.py`), plus paper-trading
  tests that need a live price (`test_auto_sl_tp.py`, `test_position_limits.py`,
  `test_multi_symbol_parallel.py`, `test_webhook_to_paper.py`, `test_paper_history.py`). These are
  environment/network limitations, not setup failures. The deterministic core (risk engine, db,
  schemas, non-network api/services, academy backtesting) passes.
- E2E/UI Playwright tests (`tests/e2e/`, `tests/ui/`) need a `package.json`, which is `.gitignore`d
  and absent from the repo, so they cannot run without first reconstructing the Playwright setup.

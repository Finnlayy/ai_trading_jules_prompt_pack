# Agent-Reflex Hybrid Trader API (`app/` package)

> **The root `AGENTS.md` is the source of truth** for project structure, broker modes,
> AI engine selection, configuration, and test strategy. This file only adds
> app-package-specific guidance. If the two disagree, trust the root file.

## Overview
FastAPI application that processes trading signals ("M8 payloads") through a deterministic pipeline:

```
M8 Webhook → AI Review (gem10_native | legacy6 | mock) → Risk Engine → Broker (factory) → Journal Logger (SQL + NDJSON)
```

## Tech Stack
- **Runtime**: Python 3.11+ with FastAPI + Uvicorn
- **Validation**: Pydantic v2 schemas (`app/schemas/`)
- **Data stores**: SQLAlchemy ORM (PostgreSQL by default; SQLite via `DATABASE_URL=sqlite:///app/data/trading.db`) plus the append-only NDJSON journal `trade_journal.jsonl` (rotated at 10 MB)
- **Virtual env**: `.venv/` at the repository root

## Key Entry Points
```
app/
├── main.py                  # App factory, JWT-protected routers, startup/shutdown tasks, SPA mount at /
├── api/
│   ├── auth.py              # POST /api/auth/google → JWT; get_current_user; get_api_key (X-API-Key for /health)
│   ├── endpoints.py         # POST /webhook/m8 — entry point, validates M8Payload
│   ├── webhook_signal.py    # POST /api/webhook/signal — external signal queue (HMAC optional)
│   └── orchestrator.py      # process_signal() — orchestrates the 4-step pipeline
├── core/
│   ├── config.py            # ALL settings are env-based via python-dotenv with typed helpers
│   │                        #   (_as_bool, _as_int, _as_float, _as_optional_float, _as_csv_list).
│   │                        #   Beware duplicated assignment blocks from old merges — search every
│   │                        #   occurrence of a name before changing a default.
│   ├── exceptions.py        # RiskGateException with reason codes
│   └── utils.py             # strip_html, iso_from_pubdate, json_dumps, async file writers
├── db/                      # engine/session/Base + ORM models + repositories
├── schemas/                 # Pydantic models for every router
└── services/                # Business logic; see root AGENTS.md for the full inventory
```

## Agent Guidelines
- **Keep schemas strict**: All payloads use Pydantic `BaseModel` with `Field` constraints.
- **Deterministic gating**: The Risk Engine uses exception-based short-circuiting (`RiskGateException`). Each gate has a unique `reason_code` string. Defaults (min confluence, max crisis, R:R, cooldown, trades/day, ...) come from env vars in `core/config.py`, not hardcoded constants.
- **State management**: `RiskEngine` and many services are module-level singletons with mutable state (`trades_today`, `last_trade_bar`, `current_bar`) — be careful with thread safety and reset them in test fixtures.
- **AI layer**: Engine selection happens in `services/ai_factory.py` (`AI_REVIEW_ENGINE=gem10_native|legacy6`, `AI_PROVIDER=mock` short-circuits to `MockAIReviewLayer`). Review services must always preserve the `SignalReview` return type and must never place orders directly.
- **Brokers**: `BaseBroker` ABC → concrete adapters → `BrokerFactory.create(mode)`. Every live-capable adapter (Pionex, Kraken, cTrader, GLINT) must stay dry-run unless its explicit `*_LIVE_TRADING_ENABLED` flag is true. Never bypass deterministic risk gates.
- **Journal format**: `trade_journal.jsonl` is append-only NDJSON. Do not overwrite; append. `JournalLogger` also mirrors entries to the SQL `Trade` table and refreshes `wiki/second_brain.md`.
- **Async safety**: wrap synchronous I/O in `await asyncio.to_thread(...)` inside async routes and background loops; mock async methods with `AsyncMock` in tests.

## Running / Testing
```bash
# From the repository root (activate .venv first)
DATABASE_URL="sqlite:///app/data/trading.db" API_KEY=dev-local-key \
  uvicorn app.main:app --reload --port 8000

# Health check (X-API-Key required)
curl -H "X-API-Key: dev-local-key" http://localhost:8000/health

# Send a signed test payload. HMAC signature is MANDATORY on /webhook/m8
# (header x-m8-signature, keyed by WEBHOOK_SECRET — dev default "test_secret").
cat > /tmp/m8_body.json <<'EOF'
{"signal_id": "test-001", "symbol": "BTCUSDT", "timeframe": "1H", "direction": "LONG", "timestamp": "2026-05-20T12:00:00Z", "entry_price": 100000, "stop_price": 99000, "target_price": 102000, "confluence_score": 85, "crisis_score": 10, "mc_dispersion": 2, "spread": 5}
EOF
printf '%s' "$(cat /tmp/m8_body.json)" > /tmp/m8_body.json   # strip trailing newline
SIG=$(python -c "import hmac,hashlib;print(hmac.new(b'test_secret',open('/tmp/m8_body.json','rb').read(),hashlib.sha256).hexdigest())")
curl -X POST http://localhost:8000/webhook/m8 \
  -H "Content-Type: application/json" \
  -H "x-m8-signature: $SIG" \
  --data-binary @/tmp/m8_body.json
```

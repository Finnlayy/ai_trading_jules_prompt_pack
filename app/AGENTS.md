# Agent-Reflex Hybrid Trader API

## Overview
FastAPI webhook receiver that processes trading signals ("M8 payloads") through a deterministic pipeline:

```
M8 Webhook → AI Review → Risk Engine → Simulation Broker → Journal Logger
```

## Tech Stack
- **Runtime**: Python 3.11+ with FastAPI
- **Validation**: Pydantic v2 schemas
- **Data store**: JSON Lines file (`trade_journal.jsonl`)
- **Virtual env**: `.venv/` (managed via `pyvenv.cfg`)

## Project Structure
```
app/
├── main.py                  # FastAPI app factory, includes /webhook router + /health
├── api/
│   ├── endpoints.py         # POST /webhook/m8 — entry point, validates M8Payload
│   └── orchestrator.py      # process_signal() — orchestrates the 4-step pipeline
├── core/
│   ├── config.py            # Hardcoded risk thresholds (RR, spread, confluence, etc.)
│   └── exceptions.py        # RiskGateException with reason codes
├── schemas/
│   ├── m8_payload.py        # Incoming webhook payload model
│   ├── ai_review.py         # SignalReview model (AI layer output)
│   ├── journal.py           # TradeJournalEntry model (broker output)
│   └── risk_flags.py        # RiskFlag model (severity, source, action)
└── services/
    ├── ai_mock.py           # MockAIReviewLayer — simplistic rule-based "AI"
    ├── risk_engine.py       # RiskEngine — deterministic gating logic
    ├── broker.py            # SimulationBroker — mock fills with slippage/fees
    └── journal_logger.py    # JournalLogger — append-only JSON Lines writer
```

## Key Data Flow
1. **POST /webhook/m8** receives `M8Payload`
2. **AI Review** (`ai_mock.py`) returns `SignalReview` (PROCEED / REJECT / HUMAN_REVIEW)
3. **Risk Engine** (`risk_engine.py`) evaluates gates in order:
   - Explicit M8 reject
   - Minimum confluence score (default 70)
   - Maximum crisis score (default 30)
   - Maximum MC dispersion (default 5)
   - Maximum spread (default 15)
   - Minimum R:R ratio (default 2.0)
   - Cooldown bars (default 3)
   - Max trades per day (default 5)
   - AI conflict (if AI rejected or flagged for human review)
4. **Simulation Broker** (`broker.py`) applies static slippage + fees, produces `TradeJournalEntry`
5. **Journal Logger** (`journal_logger.py`) appends `TradeJournalEntry` to `trade_journal.jsonl`

## Configuration (core/config.py)
| Constant | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `moonshot` | AI provider for the review swarm: `moonshot`, `openai`, or `gemini` |
| `MOONSHOT_API_KEY` | `""` | Moonshot/Kimi API key for `kimi-k2.6` |
| `OPENAI_API_KEY` | `""` | OpenAI API key for ChatGPT/GPT models |
| `GEMINI_API_KEY` | `""` | Gemini API key for Google Gemini models |
| `BROKER_MODE` | `simulation` | Broker adapter: `simulation`, `paper`, or `pionex_relay` |
| `PIONEX_RELAY_ENABLED` | `false` | Safety switch for live relay forwarding |
| `PIONEX_RELAY_URL` | `http://127.0.0.1:5000/webhook` | Local Pionex relay webhook endpoint |
| `PIONEX_SIGNAL_BOT_UUID` | `""` | Pionex Signal Bot UUID used by the relay payload |
| `MIN_RR_RATIO` | 2.0 | Minimum reward/risk ratio |
| `MAX_SPREAD` | 15.0 | Max allowed spread |
| `MIN_CONFLUENCE_SCORE` | 70.0 | Minimum M8 confluence |
| `MAX_CRISIS_SCORE` | 30.0 | Max macro crisis score |
| `MAX_MC_DISPERSION` | 5.0 | Max Monte Carlo dispersion |
| `MAX_DAILY_DRAWDOWN` | 1000.0 | Daily drawdown limit (reserved) |
| `MAX_TRADES_PER_DAY` | 5 | Trade frequency cap |
| `COOLDOWN_BARS` | 3 | Bars between trades |

## Agent Guidelines
- **Keep schemas strict**: All payloads use Pydantic `BaseModel` with `Field` constraints.
- **Deterministic gating**: The Risk Engine uses exception-based short-circuiting (`RiskGateException`). Each gate has a unique `reason_code` string.
- **State management**: `RiskEngine` holds mutable state (`trades_today`, `last_trade_bar`, `current_bar`) — be careful with thread safety if scaling beyond single-instance.
- **AI provider**: `KimiSwarmService` is provider-configurable. It must always preserve the `SignalReview` return type and must not place orders directly.
- **Pionex relay**: `PionexRelayBroker` must stay dry-run unless `PIONEX_RELAY_ENABLED=true`. Never bypass deterministic risk gates.
- **Broker simulation**: `SimulationBroker` uses static slippage (2 bps) and fees (5 bps). It does NOT close trades — results stay `"status": "OPEN"`.
- **Journal format**: `trade_journal.jsonl` is append-only NDJSON. Do not overwrite; append.

## Running / Testing
```bash
# Activate venv (Windows Git Bash)
source .venv/Scripts/activate

# Run dev server
uvicorn app.main:app --reload --port 8000

# Health check
curl http://localhost:8000/health

# Send test payload
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

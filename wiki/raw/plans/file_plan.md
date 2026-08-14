# Agent-Reflex Hybrid Trader MVP: File Plan

This file defines the concrete repository file plan for the MVP phase (Days 1-30) as outlined in the `project_plan.md`.

## Directory Structure

```text
/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── endpoints.py       # Signal ingestion routes
│   │   ├── dependencies.py    # FastAPI dependencies
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── m8_payload.py      # Pydantic schemas for raw M8 inputs
│   │   ├── ai_review.py       # Pydantic schemas for AI review layer
│   │   ├── risk_flags.py      # Pydantic schemas for risk flags
│   │   ├── journal.py         # Pydantic schemas for trade journal
│   ├── services/
│   │   ├── __init__.py
│   │   ├── risk_engine.py     # Deterministic risk engine logic
│   │   ├── broker.py          # Simulation broker (fills, fees, slippage)
│   │   ├── ai_mock.py         # Mock AI review layer for MVP
│   │   ├── journal_logger.py  # Service to write journal entries to local storage
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration settings (thresholds, cooldowns)
│   │   ├── exceptions.py      # Custom exceptions and rejection mappings
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures
│   ├── api/
│   │   ├── test_endpoints.py
│   ├── schemas/
│   │   ├── test_m8_payload.py
│   │   ├── test_ai_review.py
│   ├── services/
│   │   ├── test_risk_engine.py
│   │   ├── test_broker.py
├── requirements.txt           # MVP dependencies (fastapi, uvicorn, pydantic, pytest)
```

## Module Details

### 1. `app/schemas/m8_payload.py`
- **Purpose:** Defines the input contract for the M8 webhook payload.
- **Inputs:** None (defines schema).
- **Outputs:** Pydantic `M8Payload` class.
- **Dependencies:** `pydantic`.
- **Tests:** `tests/schemas/test_m8_payload.py` to ensure valid and invalid parsing.

### 2. `app/schemas/ai_review.py`, `risk_flags.py`, `journal.py`
- **Purpose:** Implements JSON Schema contracts defined in the project plan.
- **Inputs:** None.
- **Outputs:** Pydantic models.
- **Dependencies:** `pydantic`.
- **Tests:** `tests/schemas/test_ai_review.py`.

### 3. `app/api/endpoints.py`
- **Purpose:** FastAPI route (`/webhook/m8`) to receive signals.
- **Inputs:** JSON payload via HTTP POST.
- **Outputs:** HTTP 200/400 response.
- **Dependencies:** `fastapi`, `app.schemas`, `app.services.risk_engine`.
- **Tests:** `tests/api/test_endpoints.py` testing successful ingestion and rejection of bad schemas.

### 4. `app/services/risk_engine.py`
- **Purpose:** Deterministic final decision maker. Enforces spread, R/R, M8 scores, and cooldowns.
- **Inputs:** Validated `M8Payload`, `SignalReview` (from AI mock).
- **Outputs:** Decision enum (`PROCEED_TO_SIMULATION` or `REJECT`), `RejectReason`.
- **Dependencies:** `app.core.config`, `app.schemas`.
- **Tests:** `tests/services/test_risk_engine.py` to test every specific reject gate.

### 5. `app/services/broker.py`
- **Purpose:** Simulated execution environment. Applies fees, slippage, and mock fills.
- **Inputs:** Approved trade parameters.
- **Outputs:** `TradeJournalEntry` object.
- **Dependencies:** `app.schemas.journal`.
- **Tests:** `tests/services/test_broker.py`.

### 6. `app/services/ai_mock.py`
- **Purpose:** Non-execution AI layer placeholder for the MVP. Returns static or semi-random valid `SignalReview` objects to test pipeline flow.
- **Inputs:** `M8Payload`.
- **Outputs:** `SignalReview` model.
- **Dependencies:** `app.schemas.ai_review`.

### 7. `app/core/config.py`
- **Purpose:** Stores thresholds for Risk Engine (e.g., `MIN_RR_RATIO = 2.0`).

### 8. `requirements.txt`
- **Purpose:** Defines minimal Python dependencies.
- **Contents:** `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`.

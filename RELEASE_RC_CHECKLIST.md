# Release Candidate Checklist (V1 Direct Pionex Integration)

## 1. Local Validation
- Confirm `.env` keeps live trading disabled by default:
  - `PIONEX_DIRECT_ENABLED=true`
  - `PIONEX_DIRECT_LIVE_TRADING_ENABLED=false`
- Run full test suite:
  - `python -m pytest -q`
- Verify direct broker dry-run behavior on `/webhook/m8`.
- Confirm offline research sources are not production dependencies:
  - `tests/research/test_reference_corpus.py`
  - `tests/services/test_pionex_safety_invariants.py`
- Confirm the offline research runner remains test/mocked by default:
  - `tests/research/test_binance_futures_data.py`
  - `tests/research/test_mtf_cisd.py`

## 2. Branch and Commit
- Create release branch from `main`:
  - `git checkout -b release/v1-pionex-direct`
- Commit with a scoped message:
  - `feat: add native pionex direct broker with kelly sizing and ledger close flow`

## 3. CI and PR Gate
- Push branch and confirm CI is green.
- Open a **Draft PR** to `main` with:
  - Scope summary
  - Safety defaults (`live disabled`, `AI failure reject_live`)
  - Test evidence (pytest output)
  - Rollback note (`BROKER_MODE=simulation`)

## 4. Human Review Gate
- Manual reviewer validates:
  - `.env.example` completeness
  - No hardcoded secrets
  - Live toggle defaults are safe
  - `AI_FAILURE_POLICY` behavior in live-capable modes
  - Excluded sources stay out of training/runtime paths, especially wallet/key material
- Only promote Draft PR after explicit reviewer sign-off.

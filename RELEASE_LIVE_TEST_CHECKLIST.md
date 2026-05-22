# RELEASE LIVE TEST CHECKLIST

The following human-review checklist MUST be completed to enable `Pionex Direct` live mode execution.

- [ ] `PIONEX_DIRECT_LIVE_TRADING_ENABLED=true` ONLY AFTER dry-run evidence is reviewed and verified.
- [ ] Configure minimal order size parameter.
- [ ] Explicitly specify allowed symbol(s) in allowlist.
- [ ] `AI_FAILURE_POLICY=reject_live` MUST be set.
- [ ] Execute one ENTRY smoke test.
- [ ] Execute one CLOSE smoke test ONLY IF ENTRY succeeded.
- [ ] Immediate rollback required after smoke tests: `PIONEX_DIRECT_LIVE_TRADING_ENABLED=false`.
- [ ] Human confirmation is absolutely REQUIRED before any live POST payload is deployed to production.

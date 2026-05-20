# Validation and Risk Gates

No boilerplate. Every warning becomes a gate, test, or reject rule.

## Simulation Gates

Reject if:
- M8 score is below configured threshold.
- M8 reject reason is not null.
- no invalidation level exists.
- reward/risk is below 2.0.
- spread exceeds configured threshold.
- slippage model cannot be applied.
- fee model is missing.
- order-fill assumption is unknown.
- signal timestamp is newer than available market data.
- AI output fails schema validation.
- AI contradicts deterministic market state.
- Monte Carlo dispersion exceeds configured threshold.
- crisis score exceeds configured threshold.
- max trades per day is reached.
- entry cooldown is active.
- simulated daily drawdown exceeds configured threshold.

## Data Integrity Gates

Reject dataset if:
- OHLCV timestamps are duplicated.
- candles are missing without explicit gap handling.
- volume is zero for a volume-dependent strategy.
- split/adjustment handling is unknown for equities.
- timezone conversion is ambiguous.
- news timestamp is after signal timestamp but used in signal review.

## Backtest Gates

Reject strategy if:
- no out-of-sample test exists.
- no walk-forward test exists.
- trade count is below minimum.
- performance is not compared to baseline.
- performance collapses after fees/slippage.
- parameter set is only valid for one narrow period.
- drawdown breach occurs before target period completes.

## AI-Agent Gates

Reject AI output if:
- JSON is invalid.
- required fields are missing.
- confidence is provided without evidence.
- decision is free-text instead of enum.
- AI suggests direct execution.
- AI invents unavailable market data.
- AI references future information.
- AI changes risk parameters without approval.

## Human Review Gates

Human approval required before:
- changing Sigma/PineScript source
- changing M8 thresholds
- changing risk-engine thresholds
- enabling exchange testnet execution
- running expensive Kimi Swarm jobs
- accepting a new strategy hypothesis
- promoting simulation to paper trading

## Minimum Validation Stack

Jules must plan these tests:

1. Unit tests
   - schema validation
   - risk gate behavior
   - signal ingestion
   - rejection reason mapping

2. Integration tests
   - Pine payload -> FastAPI -> risk engine -> simulation broker -> journal

3. Backtests
   - in-sample
   - out-of-sample
   - walk-forward
   - baseline comparison

4. Failure tests
   - bad JSON
   - missing data
   - stale signal
   - AI unavailable
   - exchange/testnet unavailable
   - duplicate signal


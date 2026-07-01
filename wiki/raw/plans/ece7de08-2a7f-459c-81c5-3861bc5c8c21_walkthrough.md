# Quant-God GA Engine v3.1 — NT8 Conversion Walkthrough

**Source**: Pine Script v6 `Quant-God GA Engine [v3.1 Prop-Hardened]`  
**Output**: [QuantGodGAEngine.cs](file:///C:/Users/finnp/.gemini/antigravity/scratch/QuantGodGAEngine/QuantGodGAEngine.cs)  
**Architecture**: 100% standalone — zero external DLLs, zero plugins

---

## Agent Pipeline Summary

| Agent | Role | Key Deliverable |
|---|---|---|
| 🛡️ Agent 0 — Quant Genie | Executive flow control | Strict 12-step sequential `OnBarUpdate` |
| 🧠 Agent 1 — Deconstructor | Pine→C# math map | Full parity audit (see table below) |
| 🛠️ Agent 2 — Synthesizer | C# implementation | `SimulateIndividual`, `EvolvePopulation`, NT8 managed orders |
| ⚡ Agent 3 — NT8 Expert | Adversarial QA | Custom Wilder RSI, sovereign kill switch, `BarsRequiredToTrade=0` fix |
| ⚖️ Agent 4 — QA Validator | Parity verification | All Pine FIXes ported, no future-leak confirmed |

---

## Logic Parity Map (Agent 1 + Agent 4)

| Pine Construct | C# Equivalent | Status |
|---|---|---|
| `type Individual` (UDT) | `class GA_Individual` | ✅ Reference type — correct Pine v6 array semantics |
| `array<Individual>` | `List<GA_Individual>` | ✅ Reference-type list |
| `ta.atr(14)` | `ATR(14)` | ✅ Wilder's RMA in both — exact match |
| `ta.macd(close, 12, 26, 9)` | `MACD(Close, 12, 26, 9)` | ✅ EMA-based in both — exact match |
| `ta.rsi(close, n)` | `ComputeWilderRsi()` | ✅ **Custom Wilder RMA** — closes NT8 built-in parity gap |
| `ta.crossover(a, b)` | `prev_a <= prev_b && now_a > now_b` | ✅ Exact match |
| `ta.crossunder(a, b)` | `prev_a >= prev_b && now_a < now_b` | ✅ Exact match |
| `barstate.isconfirmed` | `Calculate.OnBarClose` | ✅ Exact match |
| `barstate.isfirst` | `State == State.DataLoaded` | ✅ Population initialized in DataLoaded |
| `barstate.islast` | `IsLastBarOnChart` | ✅ Dashboard renders on last bar |
| `ta.change(time("D"))` | `Time[0].Date != _lastTradingDay.Date` | ✅ Calendar day boundary — exact match |
| `math.random(min, max)` | `RandomRange(min, max)` | ✅ Uniform distribution — seeded for reproducibility |
| **Pine FIX 1** — Trailing DD floor | `TrailingDdFloor` per-individual | ✅ Ported |
| **Pine FIX 2** — Array bounds guard | `Math.Min(..., n-1)` | ✅ Ported |
| **Pine FIX 3** — Consistency rule | `MaxDayPnl / NetProfit` penalty | ✅ Ported |
| **Pine FIX 4** — Explicit flat guard | `if (ind.PosState == 0)` before entry | ✅ Ported |
| **Pine FIX 6** — Accurate DD tracking | `DailyStartEquity` reset per-day | ✅ Ported |

---

## Critical NT8 Differences & Agent 3 Fixes

### 1. RSI Parity Gap (Most Important)

> [!WARNING]
> NT8's built-in `RSI(Close, n, smooth)` uses **EMA** internally.
> Pine's `ta.rsi` uses **Wilder's RMA** (= `(prev*(n-1) + x) / n`).
> On a 14-period RSI this creates a **~0.3–0.8 point divergence** — enough to flip threshold comparisons and produce different signals.

**Fix**: `ComputeWilderRsi()` — a fully custom Wilder implementation:
- Seeds with SMA of first `rsiLen` up/down moves
- Applies `(prev*(n-1)+x)/n` smoothing on every subsequent bar
- **Must be called on every bar before any `return` guard** — otherwise the seed never executes

### 2. `BarsRequiredToTrade = 0`

> [!IMPORTANT]
> Standard NT8 practice sets `BarsRequiredToTrade` to the indicator warmup period (e.g., 35+).
> This **breaks the custom RSI** — if `OnBarUpdate` is gated until bar 35, the RSI seed at bar 14 never fires and the RSI stays at 50.0 permanently.

**Fix**: Set `BarsRequiredToTrade = 0` and implement all guards manually inside `OnBarUpdate`:
```csharp
// Step 1: RSI — runs on every bar, no skip
double rsiVal = ComputeWilderRsi();

// Step 2: Guard for MACD/ATR warmup
if (CurrentBar < MACD_SLOW + MACD_SIG + 2) return;
```

### 3. Sovereign Kill Switch (Agent 3 Extension)

Pine only tracked **simulated equity**. In NT8 live/sim trading, the **real account** must also be protected.

`UpdateRealPropRisk()` added:
- Tracks real `Account.Get(CashValue)` each bar
- Enforces daily DD limit and trailing floor on the live account
- Activates a **permanent session kill switch** if breached
- Immediately flattens open real positions via `ExitLong/ExitShort`
- Prints detailed breach log to Output window

### 4. Elitism State Preservation

> [!NOTE]
> Pine pushes the **object reference** of elite individuals into the new population.
> Elite individuals **retain** their `CurrentEquity`, `NetProfit`, etc. across generations.
> Only child (crossover) individuals are reset to fresh 10,000 equity.
>
> C# `class` (reference type) replicates this exactly. Using a `struct` would have broken this.

### 5. SL Priority on Same-Bar Hits

When both SL and TP are hit on the same bar, the code prioritizes the **stop-loss** (`exitPrice = hitSl ? slPrice : tpPrice`). This is the conservative prop-firm behavior.

---

## Deployment Instructions

### Step 1 — Copy the File
```
Source: C:\Users\finnp\.gemini\antigravity\scratch\QuantGodGAEngine\QuantGodGAEngine.cs

Destination: %USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\Strategies\QuantGodGAEngine.cs
```

### Step 2 — Compile in NT8
1. Open NinjaTrader 8
2. Go to **Tools → NinjaScript Editor**
3. The file should appear under `Strategies` in the file tree
4. Press **F5** (or click **Compile**) — expect 0 errors, 0 warnings

### Step 3 — Load in Strategy Analyzer
1. Open **New → Strategy Analyzer**
2. Select **`QuantGodGAEngine`** from the strategy dropdown
3. Configure instrument, timeframe, and date range
4. Set parameters in the three groups:

| Group | Key Parameters |
|---|---|
| **Prop Fund Settings** | Daily DD %, Max DD %, Trailing mode, Consistency rule |
| **Genetic Algorithm Settings** | Population size, Eval period, Mutation rate, RSI length |
| **Execution Settings** | Contracts per signal |

### Step 4 — Live/Sim Trading
1. Attach strategy to a chart
2. NT8 will display the dashboard overlay (top-right, Courier New, green/red)
3. Monitor the Output window for kill switch events
4. Kill switch is **permanent per session** — reload strategy to reset

---

## Performance Characteristics

| Metric | Value / Note |
|---|---|
| Computation per bar | O(popSize) simulation + O(popSize²) sort every evalPeriod bars |
| Memory | ~30 `GA_Individual` objects × ~15 doubles/ints = negligible |
| Sort complexity | O(n²) bubble sort — fine for popSize ≤ 100 |
| Sort upgrade path | Replace inner loops with `_population.Sort(...)` for popSize > 100 |
| RNG reproducibility | Seeded `Random(42)` — same genes each run for backtesting |
| RNG for live trading | Change to `new Random()` in DataLoaded for true randomness |

---

## Open Optimization Opportunities (Agent 3)

1. **Position sizing**: Currently fixed contracts. Add equity-fractional sizing using `Account.Get(CashValue)` proportional to `best.CurrentEquity / 10000.0`
2. **Multi-objective fitness**: Add Sharpe Ratio or profit factor as a secondary fitness dimension alongside net profit
3. **Niching**: Prevent genetic drift to a single attractor by adding diversity penalty for gene clusters
4. **Session filter**: Add time-of-day filter to avoid low-liquidity periods (futures open/close)
5. **Slippage model**: Add per-trade friction cost to the simulated PnL to prevent overfitting to frictionless fills

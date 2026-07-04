# Net Profit & Alpha Optimization Plan

To maximize the statistical win rate and average geometric return (Enchanting Net Profit) of the `Cisd24PropEngine` inside NinjaTrader 8, I have reviewed the structural translation and identified key areas where we can uncage the maximum potential of the algorithm.

## User Review Required

> [!WARNING]
> Scaling in heavily ("Pyramiding") increases drawdown magnitude. Prop Firms strictly penalize large open drawdowns. Are you willing to increase risk via localized scaling-in, or should we strictly focus on tightening execution slippage and stop-losses to boost Net Profit safely?

## Proposed Algorithmic Enhancements

### 1. [MODIFY] `Cisd24PropEngine.cs` - Re-Enable Pyramiding (Scale-in Alpha)
The original Pine Script contained parameters for `Auto Buy Dip`. I previously bypassed this to enforce a strict `pyramiding=0` protective rule.
* **Proposal**: Re-implement Native Pyramiding. If a Long setup is active and the asset retraces into an inner FVG core, we issue a secondary standard entry incrementing position size exactly when the trend reasserts itself. This magnifies compounding profit drastically during long trends.

### 2. [MODIFY] `Cisd24PropEngine.cs` - Shift from Market to Limit Entries
Presently, your algorithm executes `EnterLong(...)` which fires a standard Market order at the close of the bar. Over hundreds of trades, spread & slippage eviscerate Net Profit.
* **Proposal**: Force `EnterLongLimit(...)` utilizing the upper bound of the recent FVG or Order Block array (`bullFvgTops[0]`) as the hard limit. This ensures you only enter at premium localized liquidity.

### 3. [MODIFY] `Cisd24PropEngine.cs` - Dynamic Breakeven Acceleration
The "Tiny Trail" currently only binds *after* TP1 is hit. If price reaches 95% to TP1 and reverses, it hits a full Stop Loss.
* **Proposal**: Implement a mathematical `Breakeven Trigger`. Once the price runs 50% toward TP1, the Stop Loss is immediately pulled to `Entry + TickSize` to enforce a risk-free trade scenario. This vastly increases the Sharpe Ratio and boosts Net Profit by reducing full-R losses.

## Verification Plan
1. Parse the C# logic and write the Limit Entry modifications locally.
2. Embed the Breakeven variable bindings directly into the `OnBarUpdate()` trailing execution sequence.
3. Validate compilation to ensure execution syntax correctly maps to NinjaTrader's `EnterLongLimit` constraints. 
  
Would you like me to push these 3 aggressive Net Profit optimizations directly into the NinjaScript C# file?

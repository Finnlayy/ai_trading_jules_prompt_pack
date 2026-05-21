# UI/UX Concept: Pine Script Studio & The Disbelief Gauntlet

## 1. Core Aesthetic: The "Anti-Casino" (Terminal Design)
The UI must radiate clinical, data-driven sobriety. We are metabolizing "Model Shock" (the skepticism of professionals) through transparency and brutalism.

**Color Palette:**
- **Background:** Deep Terminal Black (`#0a0a0a`)
- **Panels/Cards:** Dark Slate/Gray (`#151618`)
- **Accents:** Matte Mint (`#3ebd93`) for positive metrics, muted Rust (`#b84d4d`) for negatives.
- **Typography:** Monospaced, highly legible (e.g., JetBrains Mono, Fira Code), stark white or light gray.
- **Absolute Bans:** No glowing neon greens/reds. No confetti animations.

**Audio Feedback:**
- **No "Ka-Ching" or cash register sounds.**
- Interactions sound like industrial machinery: heavy relay clicks for starting a backtest, deep low-pass bass thuds for a Guillotine liquidation.

## 2. Psychological Grounding: The Subjunctive Mood
To actively fight overconfidence and the illusion of certainty, the application *never* speaks in absolutes regarding historical data.

**UI Copy Rules:**
- ❌ "You made $5,000" -> ✅ "The simulated equity curve would have reached..."
- ❌ "Win Rate: 65%" -> ✅ "Historical Simulated Hit Rate: 65%"
- ❌ "Next Trade Setup" -> ✅ "Theoretical Setup Condition Met"
- ❌ "Profit" -> ✅ "Simulated PnL"

## 3. Wireframe Concept: The "Neural Flow" Dashboard

The interface is divided into three primary vertical panes:

### Left Pane: The Constructor (Code & Logic)
- **Editor:** Advanced code editor for Pine Script v6.
- **Agent Chat:** A slim panel where the Quant Architect AI can suggest logic refactoring (e.g., "Consider adding a displacement filter here").
- **Compiler Logs:** Raw output of the compilation process.

### Center Pane: The Telemetry Dashboard (Chart & Vis)
- **Chart:** Clean OHLCV data. No flashy indicators unless explicitly coded.
- **Shadow Orders Vis:** Visual representation of the "Maker-Logic" – faint lines showing where limit orders *would* have sat in the Breaker Blocks.
- **Regime Overlay:** Background shading indicating the current market regime (e.g., grayed out when CHOP > 61.8, showing the bot is in standby).

### Right Pane: The Disbelief Gauntlet (Stress Tests & KPIs)
This is the core differentiator. It is designed to let users actively try to break their strategy.

**KPI Readout (Naked Truths):**
- Sortino Ratio (Must be > 2.0 to be highlighted in mint, else gray).
- Sharpe Ratio.
- Hurst Exponent (Regime indicator).
- Max Simulated Drawdown.

**The Stress-Test Modules (Interactive Sliders & Toggles):**
- **Slippage Injector:** Slider from 0 to 50 bps. (Label: "Inject worst-case fill slippage").
- **Liquidity Vacuum:** Toggle. Simulates a flash crash where no limit orders are filled until the next major support block.
- **The Toxic Monday Filter:** Toggle. Removes all trades between 08:00 and 11:30 on Mondays. See how it affects the curve.
- **Fee Multiplier:** Simulates trading on a low-tier exchange account.

**The Guillotine Simulator:**
- A visual "burn down" chart showing how close the strategy came to the -25% Hard Kill-Switch during its worst drawdown.

## 4. The Live Event View (Gauntlet Season 1)
When the software switches to "Spectator Mode" for the e-sports broadcast:
- The UI strips away the code editor.
- Shows a leaderboard of competing algorithms.
- **The AI Swarm Feed:** A ticker at the bottom displaying the generated esports commentary (e.g., *"Bot_Alpha's Kelly-Warmup saved it from the initial chop, but the lack of dynamic breakeven is bleeding its equity."*)

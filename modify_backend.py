import re

with open("app/api/backtest_runner.py", "r") as f:
    content = f.read()

# 1. Add imports at the top
imports = """
import io
import base64
import asyncio
import matplotlib
matplotlib.use('Agg')  # Force headless backend
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
"""

# Place it after `from pydantic import BaseModel`
content = content.replace("from pydantic import BaseModel\n", f"from pydantic import BaseModel\n{imports}\n")

# 2. Add _generate_backtest_chart_sync helper function
chart_func = """
def _generate_backtest_chart_sync(outcomes: list[dict]) -> str:
    \"\"\"Generate a dual-axis Equity and Drawdown chart matching the terminal theme.\"\"\"
    if not outcomes:
        return ""

    # Extract cumulative PnL
    pnls = [0.0] + [t["pnl"] for t in outcomes]
    equity = 10000.0 + np.cumsum(pnls)
    trade_indices = np.arange(len(equity))

    # Calculate drawdown profile
    peaks = np.maximum.accumulate(equity)
    drawdowns = (equity - peaks) / peaks * 100 # percentage drawdown

    # Set Seaborn / Matplotlib styling
    plt.style.use('dark_background')
    fig, ax1 = plt.subplots(figsize=(10, 4.5), facecolor='#0a0a0a')
    ax1.set_facecolor('#151618')

    # 1. Plot Equity Curve
    curve_color = '#3ebd93' if equity[-1] >= 10000.0 else '#b84d4d'
    ax1.plot(trade_indices, equity, color=curve_color, linewidth=2, label="Simulated Equity")
    ax1.set_xlabel("Trades Count", color='#e5e7eb', fontsize=10, fontweight='bold')
    ax1.set_ylabel("Equity (USDT)", color='#e5e7eb', fontsize=10, fontweight='bold')
    ax1.tick_params(colors='#9ca3af')
    ax1.grid(True, color='#2d3139', linestyle='--', alpha=0.5)

    # 2. Plot Drawdown Profile (Secondary Y-Axis)
    ax2 = ax1.twinx()
    ax2.fill_between(trade_indices, drawdowns, 0, color='#b84d4d', alpha=0.15, label="Drawdown %")
    ax2.plot(trade_indices, drawdowns, color='#b84d4d', linewidth=1, alpha=0.7)
    ax2.set_ylabel("Drawdown (%)", color='#b84d4d', fontsize=10, fontweight='bold')
    ax2.tick_params(axis='y', colors='#b84d4d')
    ax2.set_ylim(bottom=min(-25.0, np.min(drawdowns) - 5.0), top=0.0) # Highlight the -25% Hard Kill limit

    # Title & Layout
    plt.title(f"Backtest Telemetry Curve", color='#e5e7eb', fontsize=12, fontweight='bold', pad=15)
    fig.tight_layout()

    # Save to Base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)

    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return img_b64
"""

content = content.replace("def _setup_backtest_environment", chart_func + "\ndef _setup_backtest_environment")

# 3. Update _record_historical_outcomes
orig_record_func = """def _record_historical_outcomes(executed_payloads: List):
    raw_bars = getattr(signal_generator_instance, "last_raw_bars", [])
    if not executed_payloads or not raw_bars:
        return
    from app.services.shadow_paper_engine import ShadowPaperEngine
    engine = ShadowPaperEngine()
    for payload, result in executed_payloads:
"""

new_record_func = """def _record_historical_outcomes(executed_payloads: List) -> list[dict]:
    outcomes = []
    raw_bars = getattr(signal_generator_instance, "last_raw_bars", [])
    if not executed_payloads or not raw_bars:
        return outcomes
    from app.services.shadow_paper_engine import ShadowPaperEngine
    engine = ShadowPaperEngine()
    for payload, result in executed_payloads:
"""

content = content.replace(orig_record_func, new_record_func)

# 4. Append to outcomes inside the loop
# We need to find `outcome = engine.simulate_trade(payload, raw_bars, entry_idx, max_holding_bars=50)` and append after.
orig_sim = """                outcome = engine.simulate_trade(payload, raw_bars, entry_idx, max_holding_bars=50)
                win = outcome.win"""
new_sim = """                outcome = engine.simulate_trade(payload, raw_bars, entry_idx, max_holding_bars=50)
                outcomes.append({"pnl": outcome.pnl_quote})
                win = outcome.win"""
content = content.replace(orig_sim, new_sim)

# 5. Make _record_historical_outcomes return `outcomes`
orig_scout_catch = """            except Exception:
                pass"""

new_scout_catch = """            except Exception:
                pass
    return outcomes"""
content = content.replace(orig_scout_catch, new_scout_catch)


# 6. Update `run_backtest` to capture and use `outcomes`
orig_run = """        results, executed_payloads = await _execute_payloads(payloads)
        _record_historical_outcomes(executed_payloads)

        executed = sum(1 for r in results if r["final_decision"] == "EXECUTED_SIM")"""

new_run = """        results, executed_payloads = await _execute_payloads(payloads)
        outcomes = _record_historical_outcomes(executed_payloads)
        chart_base64 = await asyncio.to_thread(_generate_backtest_chart_sync, outcomes)

        executed = sum(1 for r in results if r["final_decision"] == "EXECUTED_SIM")"""

content = content.replace(orig_run, new_run)

# 7. Include `chart_base64` in the response dict
orig_return = """            "generation_summary": generation_summary,
            "results": results,
        }"""
new_return = """            "generation_summary": generation_summary,
            "chart_base64": chart_base64,
            "results": results,
        }"""

content = content.replace(orig_return, new_return)

with open("app/api/backtest_runner.py", "w") as f:
    f.write(content)

print("Modification complete.")

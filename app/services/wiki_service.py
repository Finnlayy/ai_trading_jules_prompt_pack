import os
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import func
from app.db import SessionLocal
from app.db.models import Trade, PaperTrade, PaperPosition
from app.services.agent_registry import agent_registry

WIKI_DIR = Path("wiki")
SECOND_BRAIN_FILE = WIKI_DIR / "second_brain.md"

def _get_live_stats(db):
    total_trades = db.query(func.count(Trade.id)).scalar() or 0
    pnl_sum = db.query(func.sum(Trade.pnl)).scalar() or 0.0
    winning_trades = db.query(func.count(Trade.id)).filter(Trade.pnl > 0).scalar() or 0
    losing_trades = db.query(func.count(Trade.id)).filter(Trade.pnl <= 0).scalar() or 0
    winrate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
    return total_trades, pnl_sum, winrate

def _get_paper_stats(db):
    total_paper_trades = db.query(func.count(PaperTrade.id)).scalar() or 0
    paper_pnl_sum = db.query(func.sum(PaperTrade.pnl)).scalar() or 0.0
    paper_winning = db.query(func.count(PaperTrade.id)).filter(PaperTrade.pnl > 0).scalar() or 0
    paper_winrate = (paper_winning / total_paper_trades) * 100 if total_paper_trades > 0 else 0.0
    return total_paper_trades, paper_pnl_sum, paper_winrate

def _get_open_positions(db):
    return db.query(PaperPosition).filter(PaperPosition.status == "open").all()

def _get_agent_leaderboard():
    agents = agent_registry.get_all_identities()
    agent_rows = []
    for agent in agents:
        badges_str = ", ".join(f"{b.icon} {b.name}" for b in agent.badges) if agent.badges else "None"
        agent_rows.append(
            f"| `{agent.name}` | {agent.archetype} | {agent.total_calls} | {agent.correct_calls} | {agent.accuracy:.2%} | {agent.current_streak} | {badges_str} |"
        )
    return agent_rows

def _scan_docs():
    md_index_rows = []
    try:
        import os
        for p in sorted(Path(".").glob("*.md")):
            if p.is_file():
                stat = p.stat()
                size_kb = stat.st_size / 1024.0
                modified_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                md_index_rows.append(f"| `{p.name}` | {size_kb:.2f} KB | {modified_time} UTC |")
    except Exception as scan_err:
        md_index_rows = [f"| Error scanning docs | {scan_err} | - |"]
    return md_index_rows

def _run_compressor():
    try:
        from app.services.brain_compressor import BrainCompressor
        import asyncio

        compressor = BrainCompressor()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(compressor.run_sync_and_compile())
        else:
            asyncio.run(compressor.run_sync_and_compile())
    except Exception as compress_err:
        print(f"Error executing brain compressor: {compress_err}")

def update_second_brain():
    """Compiles statistics and learning registry from DB & registry into wiki/second_brain.md."""
    WIKI_DIR.mkdir(exist_ok=True)
    db = SessionLocal()
    try:
        total_trades, pnl_sum, winrate = _get_live_stats(db)
        total_paper_trades, paper_pnl_sum, paper_winrate = _get_paper_stats(db)
        open_paper_positions = _get_open_positions(db)
        agent_rows = _get_agent_leaderboard()
        md_index_rows = _scan_docs()

        now_str = datetime.now(timezone.utc).isoformat()
        md = f"""# Project Wiki & Second Brain (Swarm Memory)

*Last Updated: {now_str}*

This file serves as the unified project memory for all 17 Scouts and Gems, recording historical outcomes, accuracy ratings, and real-time portfolio metrics to prevent memory loss and optimize alignment.

---

## 📊 Live Portfolio Statistics

### 1. Simulated/Paper Trading Summary
- **Total Simulated Trades**: {total_paper_trades}
- **Net Simulated P&L**: ${paper_pnl_sum:.4f} USD
- **Win Rate**: {paper_winrate:.2f}%

### 2. Live Trading Summary
- **Total Live Trades**: {total_trades}
- **Net Live P&L**: ${pnl_sum:.4f} USD
- **Win Rate**: {winrate:.2f}%

---

## 💼 Open Paper Positions
| Symbol | Direction | Volume | Avg Entry | Stop Loss | Take Profit | Unrealized P&L |
| --- | --- | --- | --- | --- | --- | --- |
"""
        if not open_paper_positions:
            md += "| None | - | - | - | - | - | - |\n"
        for pos in open_paper_positions:
            md += f"| `{pos.symbol}` | {pos.direction} | {pos.volume:.4f} | {pos.avg_entry_price:.4f} | {pos.stop_loss or 0.0:.4f} | {pos.take_profit or 0.0:.4f} | ${pos.unrealized_pnl or 0.0:.4f} |\n"

        md += f"""
---

## 🤖 Academy Swarm Leaderboard
| Agent Name | Archetype | Total Calls | Correct | Accuracy | Streak | Badges |
| --- | --- | --- | --- | --- | --- | --- |
"""
        if not agent_rows:
            md += "| None | - | - | - | - | - | - |\n"
        else:
            md += "\n".join(agent_rows) + "\n"

        md += """
---

## 🧠 Memory & Swarm Directives (For Agents & Gems)
When processing trade signals, strategy updates, or configuration inputs:
1. **Consult this Second Brain**: Check the current agent accuracy and open positions list.
2. **Flag Decay**: If any agent accuracy drops below 60% after 20+ calls, prioritize executing training drills for that specific agent.
3. **Prevent Congestion**: Avoid opening new positions in symbols that correlate heavily with currently open positions.
4. **Log Learning Outcomes**: Evolution Optimizer (Phase 10) must write all learning outcomes to the database so they are compiled here.

---
"""

        md += """
## 🛠️ System Library & Code Repository (Strategies & Models)
To maintain structural integrity of custom strategies and models:
1. **Custom PineScript Strategies**: Uploaded scripts via the AI Chat or frontend are physically saved as `.pine` files in `app/scripts/generated_pines/`. The system scans this folder on startup to register them dynamically. Strategy IDs can contain alphanumeric characters, underscores, and hyphens (regex `^[a-zA-Z0-9_-]+$`), and support `pine_placeholder` models.
2. **ONNX Deployment Models**: Machine learning models and policy weights are stored in `data/academy_policy/models/`. The active model is named `policy.onnx` with its metadata preserved in `manifest.json`.
3. **System Folder Explorer**: An explorer shortcut (`POST /api/academy/policy/onnx/open-folder`) opens the active local model hub directory directly in the host OS file explorer.

---

## 🧠 Second Brain Summaries Index
A consolidated fast-browsing layer of summaries and raw data for all developer chat logs and project plans is automatically compiled here:
- **Consolidated Summaries Index**: [second_brain_summaries.md](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/wiki/second_brain_summaries.md)

---

## 📂 Project Documentation Index
This section lists all prompt pack instructions and design assets stored in the repository root directory:

| Document Name | Size | Last Modified (UTC) |
| --- | --- | --- |
"""
        if not md_index_rows:
            md += "| None found | - | - |\n"
        else:
            md += "\n".join(md_index_rows) + "\n"

        with open(SECOND_BRAIN_FILE, "w", encoding="utf-8") as f:
            f.write(md)

        print("Second brain (wiki/second_brain.md) successfully updated!")

        _run_compressor()

    except Exception as exc:
        print(f"Error updating second brain: {exc}")
    finally:
        db.close()

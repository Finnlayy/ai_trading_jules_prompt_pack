# Project Wiki & Second Brain (Swarm Memory)

*Last Updated: 2026-06-09T01:18:25.042052+00:00*

This file serves as the unified project memory for all 17 Scouts and Gems, recording historical outcomes, accuracy ratings, and real-time portfolio metrics to prevent memory loss and optimize alignment.

---

## 📊 Live Portfolio Statistics

### 1. Simulated/Paper Trading Summary
- **Total Simulated Trades**: 3
- **Net Simulated P&L**: $0.0000 USD
- **Win Rate**: 0.00%

### 2. Live Trading Summary
- **Total Live Trades**: 1106
- **Net Live P&L**: $-0.0000 USD
- **Win Rate**: 0.00%

---

## 💼 Open Paper Positions
| Symbol | Direction | Volume | Avg Entry | Stop Loss | Take Profit | Unrealized P&L |
| --- | --- | --- | --- | --- | --- | --- |
| `SOLUSD` | LONG | 0.2000 | 65.6900 | 0.0000 | 0.0000 | $0.0000 |
| `XETHZUSD` | LONG | 0.0100 | 1667.9400 | 0.0000 | 0.0000 | $0.0000 |
| `XRPUSD` | LONG | 5.0000 | 1.1534 | 0.0000 | 0.0000 | $0.0000 |

---

## 🤖 Academy Swarm Leaderboard
| Agent Name | Archetype | Total Calls | Correct | Accuracy | Streak | Badges |
| --- | --- | --- | --- | --- | --- | --- |
| `macro_sentinel` | Stratege | 259 | 132 | 50.97% | 2 | 🥉 Apprentice, ⚡ Streak |
| `market_dna` | Analyst | 259 | 105 | 40.54% | 3 | 🥉 Apprentice |
| `structural_architect` | Architekt | 259 | 144 | 55.60% | 3 | 🥉 Apprentice, 🥈 Adept |
| `harmony_coordinator` | Diplomat | 259 | 115 | 44.40% | 4 | 🥉 Apprentice |
| `indicator_fusion` | Analyst | 259 | 147 | 56.76% | 1 | 🥉 Apprentice, ⚡ Streak |
| `risk_kernel` | Wächter | 259 | 111 | 42.86% | 2 | 🥉 Apprentice, ⚡ Streak |
| `pine_core` | Entwickler | 162 | 19 | 11.73% | 1 | 🥉 Apprentice |
| `payload_qa` | Prüfer | 259 | 119 | 45.95% | 1 | 🥉 Apprentice, ⚡ Streak |
| `execution_watchdog` | Operator | 259 | 153 | 59.07% | 2 | 🥉 Apprentice, ⚡ Streak |
| `evolution_optimizer` | Forscher | 162 | 106 | 65.43% | 8 | 🥉 Apprentice, 🥈 Adept, ⚡ Streak |
| `technical` | Analyst | 271 | 270 | 99.63% | 120 | 🥉 Apprentice, ⚡ Streak, 🥈 Adept, 🥇 Expert |
| `sentiment` | Diplomat | 264 | 3 | 1.14% | 1 | 🥉 Apprentice |
| `risk` | Guardian | 265 | 264 | 99.62% | 71 | 🥉 Apprentice, ⚡ Streak, 🥈 Adept, 🥇 Expert |
| `macro` | Strategist | 625 | 625 | 100.00% | 625 | 🥉 Apprentice, ⚡ Streak, 🥈 Adept, 🥇 Expert, 💎 Master |
| `execution` | Operator | 264 | 264 | 100.00% | 264 | 🥉 Apprentice, ⚡ Streak, 🥈 Adept, 🥇 Expert |
| `correlation` | Architect | 264 | 84 | 31.82% | 1 | 🥉 Apprentice |

---

## 🧠 Memory & Swarm Directives (For Agents & Gems)
When processing trade signals, strategy updates, or configuration inputs:
1. **Consult this Second Brain**: Check the current agent accuracy and open positions list.
2. **Flag Decay**: If any agent accuracy drops below 60% after 20+ calls, prioritize executing training drills for that specific agent.
3. **Prevent Congestion**: Avoid opening new positions in symbols that correlate heavily with currently open positions.
4. **Log Learning Outcomes**: Evolution Optimizer (Phase 10) must write all learning outcomes to the database so they are compiled here.

---

---

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
| `01_jules_masterprompt.md` | 7.04 KB | 2026-05-20 17:51:37 UTC |
| `01_jules_masterprompt_ui_redesign.md` | 7.03 KB | 2026-05-26 15:34:31 UTC |
| `02_research_brief_input.md` | 3.20 KB | 2026-05-20 17:51:37 UTC |
| `03_sigma_m8_context.md` | 1.74 KB | 2026-05-20 17:51:37 UTC |
| `04_agent_roles_and_boundaries.md` | 2.39 KB | 2026-05-20 17:51:37 UTC |
| `05_json_schema_contracts.md` | 3.68 KB | 2026-05-20 17:51:37 UTC |
| `06_validation_and_risk_gates.md` | 2.51 KB | 2026-05-20 17:51:37 UTC |
| `07_jules_execution_checklist.md` | 2.31 KB | 2026-05-20 17:51:37 UTC |
| `09_ui_ux_disbelief_gauntlet.md` | 3.57 KB | 2026-05-22 00:25:00 UTC |
| `AGENTS.md` | 21.68 KB | 2026-05-31 01:55:23 UTC |
| `ai_academy_plan.md` | 15.47 KB | 2026-05-27 18:20:45 UTC |
| `file_plan.md` | 4.06 KB | 2026-05-20 22:30:38 UTC |
| `JULES_24H_SCHEDULE.md` | 47.86 KB | 2026-05-24 06:31:39 UTC |
| `pionex_layout_research.md` | 9.97 KB | 2026-05-26 15:41:08 UTC |
| `plan.md` | 0.46 KB | 2026-05-24 02:41:31 UTC |
| `plan_step_01_strategy_engine_pattern_recognition.md` | 11.08 KB | 2026-05-25 12:47:23 UTC |
| `plan_step_02_news_aware_ai_layer.md` | 11.77 KB | 2026-05-25 12:49:07 UTC |
| `plan_step_03_autonomous_trading_loop.md` | 11.82 KB | 2026-05-25 12:50:46 UTC |
| `plan_step_04_live_paper_trading_integration.md` | 15.86 KB | 2026-05-25 12:52:51 UTC |
| `project_plan.md` | 5.84 KB | 2026-05-22 00:25:00 UTC |
| `README.md` | 7.05 KB | 2026-05-24 02:45:22 UTC |
| `RELEASE_RC_CHECKLIST.md` | 1.45 KB | 2026-05-22 03:18:48 UTC |

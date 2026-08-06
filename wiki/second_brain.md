# Project Wiki & Second Brain (Swarm Memory)

*Last Updated: 2026-08-06T23:42:37.990139+00:00*

This file serves as the unified project memory for all 17 Scouts and Gems, recording historical outcomes, accuracy ratings, and real-time portfolio metrics to prevent memory loss and optimize alignment.

---

## 📊 Live Portfolio Statistics

### 1. Simulated/Paper Trading Summary
- **Total Simulated Trades**: 3
- **Net Simulated P&L**: $0.0000 USD
- **Win Rate**: 0.00%

### 2. Live Trading Summary
- **Total Live Trades**: 1043
- **Net Live P&L**: $0.0000 USD
- **Win Rate**: 0.00%

---

## 💼 Open Paper Positions
| Symbol | Direction | Volume | Avg Entry | Stop Loss | Take Profit | Unrealized P&L |
| --- | --- | --- | --- | --- | --- | --- |
| `SOLUSD` | LONG | 0.2000 | 72.3200 | 0.0000 | 0.0000 | $0.0000 |
| `XETHZUSD` | LONG | 0.0100 | 1898.2000 | 0.0000 | 0.0000 | $0.0000 |
| `XRPUSD` | LONG | 5.0000 | 1.0303 | 0.0000 | 0.0000 | $0.0000 |

---

## 🤖 Academy Swarm Leaderboard
| Agent Name | Archetype | Total Calls | Correct | Accuracy | Streak | Badges |
| --- | --- | --- | --- | --- | --- | --- |
| `macro_sentinel` | Stratege | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `market_dna` | Analyst | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `structural_architect` | Architekt | 29 | 8 | 27.59% | 1 | 🥉 Apprentice |
| `harmony_coordinator` | Diplomat | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `indicator_fusion` | Analyst | 29 | 17 | 58.62% | 5 | 🥉 Apprentice |
| `risk_kernel` | Wächter | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `pine_core` | Entwickler | 29 | 7 | 24.14% | 1 | 🥉 Apprentice |
| `payload_qa` | Prüfer | 29 | 15 | 51.72% | 2 | 🥉 Apprentice |
| `execution_watchdog` | Operator | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `evolution_optimizer` | Forscher | 29 | 3 | 10.34% | 1 | 🥉 Apprentice |
| `technical` | Analyst | 33 | 30 | 90.91% | 0 | 🥉 Apprentice, ⚡ Streak |
| `sentiment` | Diplomat | 30 | 19 | 63.33% | 5 | 🥉 Apprentice |
| `risk` | Guardian | 30 | 9 | 30.00% | 1 | 🥉 Apprentice |
| `macro` | Strategist | 29 | 19 | 65.52% | 1 | 🥉 Apprentice |
| `execution` | Operator | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `correlation` | Architect | 29 | 29 | 100.00% | 29 | 🥉 Apprentice, ⚡ Streak |
| `test-agent` | Analyst | 0 | 0 | 0.00% | 0 | None |

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
| `01_jules_masterprompt.md` | 7.04 KB | 2026-08-06 21:36:48 UTC |
| `01_jules_masterprompt_ui_redesign.md` | 7.03 KB | 2026-08-06 21:36:48 UTC |
| `02_research_brief_input.md` | 3.20 KB | 2026-08-06 21:36:48 UTC |
| `03_sigma_m8_context.md` | 1.74 KB | 2026-08-06 21:36:48 UTC |
| `04_agent_roles_and_boundaries.md` | 2.39 KB | 2026-08-06 21:36:48 UTC |
| `05_json_schema_contracts.md` | 3.68 KB | 2026-08-06 21:36:48 UTC |
| `06_validation_and_risk_gates.md` | 2.51 KB | 2026-08-06 21:36:48 UTC |
| `07_jules_execution_checklist.md` | 2.31 KB | 2026-08-06 21:36:48 UTC |
| `09_ui_ux_disbelief_gauntlet.md` | 3.51 KB | 2026-08-06 21:36:48 UTC |
| `AGENTS.md` | 33.41 KB | 2026-08-06 21:36:48 UTC |
| `JULES_24H_SCHEDULE.md` | 46.65 KB | 2026-08-06 21:36:48 UTC |
| `README.md` | 7.05 KB | 2026-08-06 21:36:48 UTC |
| `RELEASE_RC_CHECKLIST.md` | 1.45 KB | 2026-08-06 21:36:48 UTC |
| `ai_academy_plan.md` | 15.15 KB | 2026-08-06 21:36:48 UTC |
| `file_plan.md` | 4.06 KB | 2026-08-06 21:36:49 UTC |
| `pionex_layout_research.md` | 9.97 KB | 2026-08-06 21:36:49 UTC |
| `plan.md` | 0.46 KB | 2026-08-06 21:36:49 UTC |
| `plan_step_01_strategy_engine_pattern_recognition.md` | 11.05 KB | 2026-08-06 21:36:49 UTC |
| `plan_step_02_news_aware_ai_layer.md` | 11.70 KB | 2026-08-06 21:36:49 UTC |
| `plan_step_03_autonomous_trading_loop.md` | 11.81 KB | 2026-08-06 21:36:49 UTC |
| `plan_step_04_live_paper_trading_integration.md` | 15.82 KB | 2026-08-06 21:36:49 UTC |
| `pr_desc.md` | 1.06 KB | 2026-08-06 21:36:49 UTC |
| `pr_description.md` | 1.04 KB | 2026-08-06 21:59:09 UTC |
| `project_plan.md` | 5.75 KB | 2026-08-06 21:36:49 UTC |

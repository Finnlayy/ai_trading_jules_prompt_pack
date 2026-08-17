# Backend Features Summary

Based on an analysis of the `app/api` and `app/services` modules, here is a comprehensive list of features implemented in the backend:

## 1. Trading & Execution (Broker Layer)
- **Multi-Broker Integrations**: Native support for Pionex (Direct & Relay), Kraken, Bybit, and cTrader (REST & FIX protocols), as well as a mock/paper broker.
- **Smart Order Router (SOR)**: Intelligent routing of orders across integrated exchanges.
- **Paper Trading Engine**: Simulated execution environments for dry-runs.
- **Live Fill Tracker & Reconciliation Daemon**: Background jobs to sync live positions with the internal ledger and monitor order state.
- **Orderbook Simulator**: Used for realistic slippage and spread assumptions during paper trading.
- **Webhook Signal Consumer**: Receives and processes external signals (e.g., from TradingView).

## 2. Risk Management & Sizing
- **Risk Engine (Disbelief Gauntlet)**: Hard deterministic gates to reject unsafe trades before execution.
- **Portfolio Circuit Breaker**: Halts all trading activity during critical system-wide drawdowns.
- **Correlation Risk Checker**: Dynamically limits exposure by capping execution quantities on highly correlated assets.
- **Kelly Sizer (Pionex)**: Calculates position sizing utilizing Kelly criterion (e.g., half-Kelly limits).
- **SL/TP Calculator**: Dynamic and automated generation of Stop-Loss and Take-Profit limits.

## 3. AI & Agentic Orchestration
- **Agentic Reasoning Swarm**: Multi-agent architecture (Risk Scout, Technical Scout, Sentiment Scout, and an Orchestrator).
- **Multi-LLM Support**: Integration with Moonshot (Kimi), OpenAI, and Gemini.
- **Prompt RAG & Evolution**: Retrieval-Augmented Generation for dynamic AI prompting and memory injection.
- **Perception Engine**: Validates incoming signals through multiple AI perspectives.
- **Second Brain / Wiki Service**: Persistent context and knowledge base for the AI agents.
- **Shadow Paper Engine & Queue**: Evaluates rejected trades offline for continuous reinforcement learning.

## 4. Market Analysis & Strategy
- **Strategy Engine**: Executes internal logic and algorithms (e.g., MTF CISD framework).
- **Backtest Engine & Runner**: Full backtesting suite for historical data with optimization capabilities.
- **Pattern Recognition**: Detects structural market patterns.
- **Regime Engine**: Categorizes market states (Green, Yellow, Orange, Red) to adapt aggressiveness and risk thresholds.
- **Asset Calibrator & Statistical Battery**: Statistical evaluation of market volatility and metrics.

## 5. News & Sentiment
- **News Aggregator**: Pulls news from external RSS and text sources.
- **News Impact Scorer**: Evaluates the macroeconomic impact of parsed news on targeted assets.
- **Telegram News Receiver**: Ingests alpha and news directly from Telegram signals.
- **News Sentiment Lexicon**: Dictionary-based and AI-driven sentiment analysis.

## 6. Training & Reinforcement Learning (Academy)
- **Academy Curriculum & Drills**: Simulated environments designed to train the AI under specific historical market conditions.
- **Policy Service & ONNX Runtime**: Uses RL (Reinforcement Learning) models and evaluates policies efficiently via ONNX.
- **Reward Modeling**: Evaluates and rewards AI behavior based on trade simulation outcomes.

## 7. Telemetry, Monitoring & Autonomous Operations
- **Autonomous Loop**: A background continuous loop running the system autonomously without manual triggers.
- **Journal Logger**: High-performance JSONL logging for all trades and system actions.
- **Telegram Notifier & Advisors**: Real-time heartbeat and trade alerts sent to Telegram.
- **Dashboard SSE (Server-Sent Events)**: Live streaming of metrics to the frontend UI.
- **Loop Health Monitor**: Watchdog for background tasks and loops.

---

# Suggested Structured UI Integrations for Missing Features

To allow users to fully utilize the backend capabilities, the following features need to be structurally integrated into the UI (`frontend.html`):

### 1. Broker & Signal Management
*   **Pionex & Bybit Management Panels**: Create dedicated components (e.g., `<PionexPanel>`, `<BybitPanel>`) similar to the existing `<CTraderPanel>` and `<KrakenPaperPanel>` to manage specific settings and view status for these integrations.
*   **Smart Order Router (SOR) Visualization**: Add a widget to the `Overview` or `Orders` section that visualizes the SOR's routing decisions and current status across exchanges.
*   **Webhook Signal Monitor**: Create a dedicated view or table (e.g., `<WebhookMonitor>`) to track incoming external signals (like TradingView alerts), their parsing status, and subsequent actions.

### 2. Advanced Risk Visibility
*   **Circuit Breaker Status Indicator**: Add a prominent, global UI element (e.g., a banner or a badge in the header) showing the current state of the `Portfolio Circuit Breaker` (Normal/Halted) with manual override controls if permitted.
*   **Correlation Risk Dashboard**: Introduce a section within the `RiskControlPanel` to visualize current asset correlations and display any active execution caps imposed by the `Correlation Risk Checker`.
*   **Sizing & SL/TP Configurator**: Add a dedicated settings panel or modal to configure the `Kelly Sizer` parameters and dynamic `SL/TP Calculator` rules.

### 3. AI Insights & RAG
*   **Prompt RAG & Evolution Viewer**: Create a panel (e.g., `<RAGContextPanel>`) within the AI section to allow users to inspect the context injected into the LLMs and track the evolution of prompts.
*   **Perception Engine Inspector**: Implement a detailed drill-down view (perhaps clicking on a signal) that shows the raw output and validation checks from the `Perception Engine`'s multiple AI perspectives.

### 4. Market State & Statistics
*   **Market Regime Indicator**: Add a clear visual indicator to the `Overview` or `ChartPanel` showing the current market regime categorized by the `Regime Engine` (e.g., colored dots or banners for Green, Yellow, Orange, Red).
*   **Pattern & Statistics Dashboard**: Create a new panel (e.g., `<MarketStatsPanel>`) to display outputs from the `Pattern Recognition` module and the `Statistical Battery` (e.g., volatility metrics, detected structures).

### 5. External Comms & Integrations
*   **Telegram Integration Manager**: Add a settings panel to configure the `Telegram Notifier` and view the status of the `Telegram News Receiver`.

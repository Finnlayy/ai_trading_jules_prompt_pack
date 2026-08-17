# Gap Analysis: Backend Features vs. UI Representation

Based on the `backend_features_list.md` and the identified UI components in `frontend.html` (`ui_features.md`), here is a comparison to identify features not currently represented in the UI:

## 1. Trading & Execution (Broker Layer)
- **Multi-Broker Integrations**: Pionex, Kraken, Bybit, and cTrader.
  - *UI Representation*: `CTraderPanel`, `KrakenPaperPanel`, `LivePaperPanel`. (Pionex and Bybit specific panels seem missing).
  - *Action*: Need structured integration for Pionex and Bybit management.
- **Smart Order Router (SOR)**
  - *UI Representation*: None.
  - *Action*: Needs a panel or indicator showing SOR decisions/status.
- **Webhook Signal Consumer**
  - *UI Representation*: None explicitly.
  - *Action*: Needs a view to monitor incoming webhook signals (TradingView, etc.).

## 2. Risk Management & Sizing
- **Portfolio Circuit Breaker**
  - *UI Representation*: Implicit in `RiskControlPanel`, but a dedicated status indicator/override might be missing.
  - *Action*: Ensure Circuit Breaker state is clearly visible.
- **Correlation Risk Checker**
  - *UI Representation*: None.
  - *Action*: Needs a visualization in `RiskControlPanel` showing current asset correlations and active caps.
- **Kelly Sizer (Pionex) / SL/TP Calculator**
  - *UI Representation*: Partially in `OrderTable` / `OpenPositionsTable`.
  - *Action*: Could use a dedicated "Sizing & Limits" configurator/viewer.

## 3. AI & Agentic Orchestration
- **Prompt RAG & Evolution**
  - *UI Representation*: None.
  - *Action*: Needs a panel to view/manage RAG contexts and prompt evolution history.
- **Perception Engine**
  - *UI Representation*: None explicitly (maybe part of `AgentsPanel` or `AILayer`).
  - *Action*: Needs a detailed view of the multi-perspective validation process.

## 4. Market Analysis & Strategy
- **Pattern Recognition & Regime Engine**
  - *UI Representation*: `StrategyHealthPanel` might cover some, but specific Pattern/Regime indicators are missing.
  - *Action*: Needs a dashboard widget showing the current Market Regime (Green, Yellow, Orange, Red) and detected patterns.
- **Asset Calibrator & Statistical Battery**
  - *UI Representation*: None.
  - *Action*: Needs a panel for statistical market metrics and volatility readings.

## 5. News & Sentiment
- **Telegram News Receiver / Sentiment Lexicon**
  - *UI Representation*: `NewsPanel` handles some news.
  - *Action*: Add Telegram specific feed/status and Sentiment Lexicon visualizer within or alongside `NewsPanel`.

## 6. Training & Reinforcement Learning (Academy)
- *UI Representation*: `TrainingPanel`, `PolicyAnalyticsPanel`, `LifecycleLearningPanel`.
  - Seems reasonably well covered.

## 7. Telemetry, Monitoring & Autonomous Operations
- **Autonomous Loop**
  - *UI Representation*: `Control` / Toggles.
  - Seems covered.
- **Telegram Notifier & Advisors**
  - *UI Representation*: None.
  - *Action*: Needs a configuration/status panel for Telegram notifications.

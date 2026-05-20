# Research Brief Input: AI-Agenten im Trading-Ecosystem 2026

Dieses Briefing ist Eingabekontext fuer Jules. Modell- und Quellenclaims muessen von Jules verifiziert werden, bevor sie als Fakten in den finalen Projektplan uebernommen werden.

## Kernthese

Die KI-Trading-Landschaft verschiebt sich von "Chatbot schreibt Code" zu "Agenten fuehren Research-, Backtest- und Review-Workflows aus".

Das Zielsystem nutzt AI-Agenten nicht als Direct Trader, sondern als:
- Research-Agenten
- Pattern-/Sentiment-Klassifizierer
- Backtest-Orchestratoren
- Code-/Debug-Assistenten
- Journal-Reviewer
- Risk-Flag-Detektoren

Die Execution bleibt deterministisch.

## Modellrollen als Arbeitshypothese

### GPT-5.5

Geplante Rolle:
- Orchestrator
- Code Review
- Debugging
- Tool-Use-Planung
- Architekturkritik
- Backtest-Controller

Jules soll pruefen:
- aktuelle API-Verfuegbarkeit
- Tool-Use-Faehigkeiten
- Kosten/Latenz
- Eignung fuer Repo-/Terminal-Workflows

### Kimi Swarm

Geplante Rolle:
- Bulk Research
- viele parallele Hypothesen
- Sentiment-Swarms
- Strategy-Mutation
- Journal- und Log-Mining

Jules soll pruefen:
- tatsaechliche Swarm-Implementierbarkeit
- API- oder lokale Verfuegbarkeit
- Kosten pro Research-Lauf
- Qualitaet bei langen Kontexten

### Manus

Geplante Rolle:
- autonome Research-Workflows
- Repo-Aufgaben
- Backtest-Berichte
- Dokumentation
- Aufgabenketten mit Human-Approval-Checkpoints

Jules soll pruefen:
- reale Tooling-Faehigkeiten
- Integrationswege
- Grenzen der Autonomie
- geeignete Approval-Gates

## Realistische LLM-Rollen im Trading

1. Pattern Recognition und Vision
   - Chart-Screenshots koennen als Confluence genutzt werden.
   - Numerische OHLCV-Bestaetigung bleibt Pflicht.

2. Agentic Backtesting und Research
   - AI kann Hypothesen erzeugen, Backtest-Jobs planen und Ergebnisse zusammenfassen.
   - Akzeptanz nur nach deterministischer Validierung.

3. Signal-Klassifikation und Sentiment
   - AI klassifiziert News, Makro-Events, Narrative und Relevanz.
   - Output muss strukturiert und schema-validiert sein.

4. Trade Journaling und Post-Trade Review
   - AI findet Muster in Fehlern, Drawdowns und Setup-Klassen.
   - PnL und Metriken werden rechnerisch verifiziert.

## Hype, der ersetzt werden muss

### Hype: LLM als Direct Trader

Bessere Version:
- LLM erzeugt ein strukturiertes Signal Review.
- Risk Engine validiert.
- Simulation Broker fuehrt nur bei bestandenen Gates aus.

### Hype: Full Autonomous AI Hedge Fund

Bessere Version:
- Agentic Research Lab fuer Simulation.
- Human Review fuer Strategieaenderungen.
- Deterministische Execution-Gates.

### Hype: LLM-HFT

Bessere Version:
- 1h, 4h oder Daily Timeframes.
- AI fuer Kontext, Review, Research und Journaling.

## Empfohlenes MVP

Name: Agent-Reflex Hybrid Trader

Scope:
- 1h oder 4h Timeframe
- Sigma/PineScript als Signalquelle
- M8 Quality Gate als erster Filter
- Python/FastAPI Backend
- Simulation Broker
- ein AI Review Layer
- deterministische final decision
- Journal und Post-Trade Review

## Validierungsanforderungen

Jedes Projekt braucht:
- out-of-sample test
- walk-forward test
- baseline comparison
- fees model
- slippage model
- spread model
- lookahead-bias check
- data-leakage check
- minimum trade count
- rejection criteria


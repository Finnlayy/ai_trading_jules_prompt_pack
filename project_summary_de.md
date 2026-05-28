# Pine Script Studio & The Gauntlet: Projektüberblick

### 1. Projektziel & Philosophie
Das Projekt baut ein KI-gestütztes Trading-Ökosystem auf, das als "High-Performance Constructor's Garage" bezeichnet wird. Es richtet sich an professionelle Quants und verfolgt eine strikte "Anti-Casino"-Ästhetik (kein Gamification, dunkle Terminal-Optik).
Der Kern des Systems ist **"The Drawdown Survival Gauntlet"** – ein hartes Evaluierungs-Framework, in dem Trading-Strategien anhand ihrer Überlebensfähigkeit in extremen Marktphasen getestet werden (z. B. durch strikte -25% Max Drawdown "Guillotine" Liquidation).

### 2. Kernarchitektur: "The Iron Separation"
Das System unterliegt einer strikten Trennung ("The Iron Separation"), die sicherstellt, dass KI-Halluzinationen niemals echte Assets gefährden:

*   **The Judge (Deterministisches Python-Backend):**
    Die einzige Instanz, die Trades ausführt, Ticks verarbeitet und Regeln durchsetzt. "The Judge" arbeitet vollständig deterministisch, berechnet PnL, simuliert Slippage (Freq-Penalty) und wendet die "Guillotine"-Regel an.
*   **The Swarm (KI-Agenten):**
    Eine rein lesende, orchestrierende und analysierende Ebene. Der Schwarm (gesteuert durch Modelle wie Kimi, GPT-5.5 oder Gemini) darf *niemals* Live-Orders platzieren. Die KI analysiert stattdessen deterministische Logs (via JSON-Handoff-Schemas) und liefert Erkenntnisse, Hypothesen und E-Sports-ähnliche Kommentare zur Performance.

### 3. Broker-Integration & Ausführungsmodi
Das Projekt unterstützt mehrere Broker-Modi, ist aber standardmäßig extrem defensiv konfiguriert (`BROKER_MODE=simulation`):

*   **Simulation / Backtesting:** Der Standard. Bereitet Daten auf (z.B. Offline-Binance-Futures) und testet Logik auf historischen Daten ohne echte Orders.
*   **Paper Trading:** Nutzt das Bybit Testnet, um den Live-Trading-Loop gefahrlos zu evaluieren.
*   **Pionex Relay (`pionex_relay`):** Sendet JSON-Webhooks an einen lokalen Signal-Bot, jedoch standardmäßig im Dry-Run.
*   **Pionex Direct (`pionex_direct`):** Native API-Ausführung, gesichert durch striktes Whitelisting von Symbolen (z.B. Normalisierung von `XAGUSDT.P` zu `XAG_USDT_PERP`) und einen expliziten Live-Trading-Schalter (`PIONEX_DIRECT_LIVE_TRADING_ENABLED=false` als Default).

### 4. Harte Sicherheitsregeln & Guardrails
Das Repository hat sehr strenge operative Sicherheitsrichtlinien (z.B. in `AGENTS.md` und `JULES_24H_SCHEDULE.md`):

*   **Simulation First:** Jeder neue Code muss erst in der Simulation bewiesen werden. Ein Live-Bypass ist strengstens verboten.
*   **Keine KI-Live-Orders:** Der deterministische "War Room" hat immer das letzte Wort. Fällt die Konfidenz der KI unter einen Schwellenwert (`WAR_ROOM_AI_MIN_CONFIDENCE`), wird der Entry-Pfad blockiert.
*   **Subjunctive Mood:** Die KI-Kommunikation im UI muss zwingend im Konjunktiv (z.B. "Die simulierte Win-Rate beliefe sich auf...") gehalten sein, um Übermut (Overconfidence) beim Anwender zu vermeiden.

### Aktueller Status des Codes & Repositories
*   **Planung vs. Code:** Das Repository enthält detaillierte Markdown-Pläne (`plan_step_01...` bis `04`), einen ausführlichen `README.md`-Masterprompt und fertige Konzept-Skripte. Das Backend (`app/`) existiert bereits teilweise, aber vieles befindet sich in einer strukturierten Übergangsphase (Refactoring hin zu Pionex Direct & Paper Broker Integration).
*   **Tests:** Ein Test-Ordner existiert und muss bei jeder Änderung mit pytest validiert werden, um sicherzustellen, dass Backend-Verhalten nicht unbeabsichtigt modifiziert wird.
*   **Daily Tasks (Jules Schedule):** Die Entwicklung ist in strikte 24-Stunden-Zyklen unterteilt, in denen immer nur *ein* begrenzter, risikoarmer Task isoliert ausgeführt wird (z.B. "Hour 19 - Dry-Run Smoke Test").

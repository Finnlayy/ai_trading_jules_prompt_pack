# AI Core + Trainingsakademie — Vollständiger Implementierungsplan

## Ziel
Ein vollständiges "AI Training Academy"-System für den MetricFlow Bot mit:
1. **Agentenkarteibuch** — Zentrales Register aller Scouts/Agenten mit vollständiger Historie
2. **Trainingsakademie** — Strukturiertes Lernen durch synthetische Drills, Prompt-Evolution und A/B-Tests
3. **Auto-Loop Trainingscyclen** — Autonome Trainingsschleifen die Agenten 24/7 verbessern
4. **AI Core Completion** — Fehlende Basisfunktionen des AI-Cores

---
## Aktueller Stand (Was existiert bereits)
### ✅ Fundament vorhanden
- **4 Scouts**: Technical, Sentiment, Risk, Macro (`ai_kimi.py`)
- **ConfidenceRegistry**: Per-Symbol Accuracy, Experience, Specialization Score
- **Outcome Feedback**: Backtest → Live → Paper → Registry Loop
- **Context Injection**: Scout-Gewichte + Historie werden in Prompts injiziert
- **AI Layer Memory**: Chat-Verlauf + Behavior Profile
- **Autonomous Loop**: Vollautomatische Signal-Generierung + Execution
- **Weighted Orchestration**: Bessere Scouts haben mehr Einfluss auf finale Entscheidung

### ❌ Was fehlt
- Kein zentrales Agenten-Register mit Karriere-Verlauf
- Keine synthetischen Trainings-Szenarien (nur Live-/Backtest-Learning)
- Keine Prompt-Evolution (Prompts sind statisch)
- Keine A/B-Test-Infrastruktur für Scout-Prompts
- Keine Visualisierung der Agenten-Progression im UI
- Kein "Scout Upgrade"-System (SPECIALIST = nur Label, keine neuen Fähigkeiten)
- Keine Cross-Symbol Generalisierungs-Metriken
- Keine Ensemble-Diversity-Metriken

---
## Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI TRAINING ACADEMY                                │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Agenten-     │  │ Trainings-   │  │ Auto-Loop    │              │
│  │ Karteibuch   │  │ Akademie     │  │ Zyklen       │              │
│  │              │  │              │  │              │              │
│  │ • Karriere   │  │ • Drills     │  │ • Curricula  │              │
│  │ • Stats      │  │ • Badges     │  │ • Evolution  │  │ • Meta-Learn │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│         └─────────────────┼─────────────────┘                        │
│                           ▼                                          │
│              ┌────────────────────────────┐                         │
│              │   ConfidenceRegistry 2.0   │                         │
│              │  (erweitert um Academy)    │                         │
│              └────────────────────────────┘                         │
│                           │                                          │
│                           ▼                                          │
│              ┌────────────────────────────┐                         │
│              │      AI Core (Kimi)        │                         │
│              │   4 Scouts + Orchestrator  │                         │
│              └────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
```

---
## Phase 1: Agentenkarteibuch (Agent Registry)
**Ziel**: Jedem Scout eine echte "Identität" mit Karriere-Verlauf geben.

### 1.1 ScoutIdentity Model
- [ ] `app/services/agent_registry.py` erstellen
- [ ] `ScoutIdentity` Dataclass:
  - `scout_id` (UUID)
  - `name` (technical, sentiment, risk, macro)
  - `archetype` (Analyst, Diplomat, Wächter, Stratege)
  - `created_at`, `born_from` (erster Prompt-Hash)
  - `generation` (wie oft Prompt evolviert)
  - `specialization_symbols` (Top-5 Symbole nach Experience)
  - `badges` (Liste von Erfolgen)
  - `personality_vector` (künstliche Persönlichkeit für Rollenspiel)

### 1.2 Karriere-Verlauf (CareerLog)
- [ ] `CareerEntry` pro wichtigem Ereignis:
  - First Call (erste Review)
  - First Win (erstes richtiges Urteil)
  - Specialist Badge (erhalten wenn specialization_score ≥ 0.7)
  - Master Badge (≥ 100 Calls, ≥ 70% Accuracy)
  - Legendary Badge (≥ 500 Calls, ≥ 75% Accuracy, 5+ Symbole)
  - Prompt Evolution (jede Prompt-Änderung)
  - A/B Test Teilnahme
- [ ] JSON-Lines persistence: `logs/agent_careers.jsonl`

### 1.3 Badges & Achievements
- [ ] Badge-System:
  - 🥉 **Apprentice** (10+ Calls)
  - 🥈 **Adept** (50+ Calls, 60%+ Accuracy)
  - 🥇 **Expert** (100+ Calls, 70%+ Accuracy)
  - 💎 **Master** (500+ Calls, 75%+ Accuracy)
  - 🔥 **Specialist** (Spezialisierung auf 1 Symbol mit 0.7+ score)
  - 🌐 **Globalist** (Gute Performance auf 5+ Symbolen)
  - ⚡ **Streak** (10 richtige Urteile in Folge)
  - 🛡️ **Conservative** (80%+ Rejection-Rate bei schlechten Setups)

### 1.4 API Endpoints
- [ ] `GET /agents/registry` — alle Scouts mit Identität
- [ ] `GET /agents/{scout_id}/career` — Karriere-Verlauf
- [ ] `GET /agents/{scout_id}/badges` — Badges
- [ ] `GET /agents/leaderboard` — Rangliste (sortierbar nach Accuracy, Experience, Specialization)
- [ ] `GET /agents/comparison?scouts=a,b,c` — Scout-vs-Statistik

### 1.5 UI Integration
- [ ] Neuer Tab "Agenten" im Frontend
- [ ] Scout-Karten mit Avatar, Name, Badges, Stats
- [ ] Karriere-Timeline (wie GitHub Contributions-Graph)
- [ ] Leaderboard-Tabelle

---
## Phase 2: Trainingsakademie (Training Academy)
**Ziel**: Strukturiertes Lernen jenseits von "nur Live-Trading".

### 2.1 Synthetische Drills (Synthetic Drills)
- [ ] `app/services/training_drills.py`
- [ ] Drill-Typen:
  - **Pattern Recognition Drill**: Historische Bar-Sequenzen mit bekanntem Outcome — Scout muss Richtung vorhersagen
  - **Crisis Detection Drill**: Szenarien mit hohem Crisis-Score — Risk Scout muss ablehnen
  - **Sentiment Analysis Drill**: News-Headlines + Preisreaktion — Sentiment Scout muss Stimmung erfassen
  - **Regime Identification Drill**: Marktphasen (Trend, Range, Chop) — Macro Scout muss Regime identifizieren
- [ ] Drill-Engine:
  - Lädt historische Daten aus `logs/journal.jsonl`
  - Findet "Lehrreiche" Momente (z.B. False Positives der Vergangenheit)
  - Erstellt Szenarien aus echten Daten aber mit verstecktem Outcome
  - Scout gibt Urteil → sofortiges Feedback (richtig/falsch)
  - Ergebnis wird in `CareerLog` gespeichert

### 2.2 Prompt-Evolution
- [ ] `app/services/prompt_evolution.py`
- [ ] Mechanismus:
  - Analysiere Fehlurteile eines Scouts (z.B. Technical Scout verpasst Range-Breaks)
  - Generiere "Lesson" aus Fehlern via LLM
  - Füge Lesson als Beispiel in System-Prompt ein
  - Versioniere Prompts (v1, v2, v3...)
  - A/B-Test: Alter Prompt vs. Neuer Prompt auf gleichen historischen Daten
- [ ] Prompt-Registry:
  - `logs/prompt_registry.json` — alle Prompt-Versionen
  - Hash-basierte Versionierung
  - Performance pro Version tracken

### 2.3 A/B Testing Framework
- [ ] `app/services/ab_testing.py`
- [ ] A/B-Test-Lifecycle:
  1. **Hypothese**: "Technical Scout v2.1 erkennt Range-Breaks besser"
  2. **Split**: 50% der Calls → v2.1, 50% → v2.0
  3. **Run**: Mindestens 50 Calls pro Variante
  4. **Evaluate**: Accuracy, Confidence-Kalibrierung, Winrate
  5. **Decision**: Winner wird neuer Default
- [ ] API:
  - `POST /academy/ab-test/start` — neuen Test starten
  - `GET /academy/ab-test/{id}/results` — Zwischenergebnisse
  - `POST /academy/ab-test/{id}/conclude` — Test abschließen

### 2.4 Curriculum-System
- [ ] `app/services/academy_curriculum.py`
- [ ] Curricula pro Scout:
  - **Beginner**: 10 Drills auf BTCUSDT (1h)
  - **Intermediate**: 25 Drills auf 3 Symbolen, mixed Timeframes
  - **Advanced**: 50 Drills auf Volatilitäts-Events, Flash-Crashes
  - **Master**: Live-Validation mit verstecktem Stop/Target
- [ ] Fortschritts-Tracking:
  - Prozent abgeschlossen pro Curriculum
  - Bestandene/failte Drills
  - Durchschnittliche Confidence-Kalibrierung

### 2.5 UI Integration
- [ ] Neuer Tab "Akademie" im Frontend
- [ ] Drill-Interface: Szenario anzeigen → Scout-Antwort → sofortiges Feedback
- [ ] Prompt-Evolution-History: Diff zwischen Versionen anzeigen
- [ ] A/B-Test-Dashboard: Live-Charts der Varianten-Performance
- [ ] Curriculum-Fortschrittsbalken

---
## Phase 3: Auto-Loop Trainingscyclen
**Ziel**: Der Bot trainiert sich selbstständig wenn keine Live-Signale kommen.

### 3.1 Training Loop Service
- [ ] `app/services/training_loop.py`
- [ ] `TrainingLoop` — eigenständiger Background-Task (neben AutonomousTradingLoop)
- [ ] Trigger-Bedingungen:
  - Keine Live-Signale in letzten 10 Minuten
  - Nachts (22:00–06:00 UTC) wenn Märkte langsam
  - Explizit via `POST /academy/train/start`
- [ ] Trainings-Cycle:
  1. Wähle zufälligen Drill aus Curriculum
  2. Führe Drill gegen alle 4 Scouts
  3. Speichere Ergebnisse in CareerLog
  4. Wenn Genügend Daten → Prompt-Evolution prüfen
  5. Wenn Prompt-Evolution → A/B-Test starten
  6. Warte 5 Minuten → nächster Cycle

### 3.2 Nacht-Training (Night Academy)
- [ ] Konfigurierbar in `.env`:
  ```
  TRAINING_LOOP_ENABLED=true
  TRAINING_LOOP_NIGHT_MODE=true
  TRAINING_LOOP_NIGHT_START=22:00
  TRAINING_LOOP_NIGHT_END=06:00
  TRAINING_LOOP_DRILLS_PER_HOUR=12
  ```
- [ ] Nachts: Kein Live-Trading, nur Training
- [ ] Tagsüber: Live-Trading + Training in Pausen

### 3.3 Auto-Prompt-Evolution
- [ ] Wenn Scout auf 5+ Drills hintereinander falsch lag:
  1. Identifiziere gemeinsames Muster (via LLM)
  2. Generiere verbesserten Prompt-Abschnitt
  3. Starte automatischen A/B-Test (vCurrent vs. vNew)
  4. Nach 100 Calls: Entscheide ob Upgrade
  5. Wenn Upgrade: Speichere als neue Version, archiviere alte

### 3.4 Ensemble Diversity Monitor
- [ ] Metrik: Wie oft stimmen Scouts überein?
  - High Agreement (>90%): Vielleicht zu ähnlich → Diversität erhöhen
  - Low Agreement (<50%): Zu divergent → konsistenz prüfen
  - Sweet Spot (60-80%): Gutes Ensemble
- [ ] Wenn Diversität zu niedrig: Training auf "edge cases" die Scouts spalten

### 3.5 UI Integration
- [ ] Live-Training-Status im Dashboard
- [ ] "Nacht-Training läuft"-Indikator
- [ ] Training-Log: Letzte 50 Drills mit Ergebnissen
- [ ] Scout-Upgrade-Animationen (wie Level-Up in RPGs)

---
## Phase 4: AI Core Completion
**Ziel**: Fehlende Basisfunktionen des AI-Cores ergänzen.

### 4.1 Scout-Architektur Erweiterung
- [ ] **5. Scout: Execution Scout** — Bewertet Slippage, Liquidität, Orderbuch-Tiefe
- [ ] **6. Scout: Correlation Scout** — Prüft Portfolio-Korrelationen (nicht alles LONG BTC setzen)
- [ ] Optional: Scouts modular ein-/ausschaltbar machen

### 4.2 Multi-Model Unterstützung
- [ ] Pro Scout unterschiedliches Model wählbar:
  - Technical Scout → Gemini 2.5 Pro (beste Reasoning)
  - Sentiment Scout → Moonshot K2.6 (schnell, günstig)
  - Risk Scout → GPT-5.2 (konservativ, zuverlässig)
- [ ] `AI_PROVIDER` pro Scout konfigurierbar in `.env`:
  ```
  AI_PROVIDER_TECHNICAL=gemini
  AI_PROVIDER_SENTIMENT=moonshot
  AI_PROVIDER_RISK=openai
  AI_PROVIDER_MACRO=gemini
  ```

### 4.3 Scout-Prompt Versionierung
- [ ] Alle Scout-Prompts in `app/ai_prompts/` als `.md`-Dateien
- [ ] Hot-Reload: Prompt-Änderungen ohne Server-Neustart
- [ ] Versionierte Prompts:
  ```
  app/ai_prompts/
    technical/
      v1_base.md
      v2_range_breaks.md
      v3_current.md  ← Symlink zur aktiven Version
    sentiment/
      v1_base.md
      ...
  ```

### 4.4 Advanced Context Injection
- [ ] **Market Context**: Aktuelle Fear & Greed, Funding Rates, Open Interest
- [ ] **Portfolio Context**: Aktuelle Exposure, offene Positionen, heutiger PnL
- [ ] **Peer Context**: Was sagen die anderen Scouts gerade? (für Orchestrator)
- [ ] **Temporal Context**: Tageszeit, Wochentag, Jahreszeit (Seasonality)

### 4.5 Scout-Explainability
- [ ] Jeder Scout muss eine "Explanation" liefern (warum PROCEED/REJECT)
- [ ] Explanation wird im Journal gespeichert
- [ ] UI zeigt Scout-Entscheidungen als "Argumentations-Kette"
- [ ] Nutzer kann fragen: "Warum hat Risk Scout abgelehnt?" → Chat-Interface

---
## Phase 5: Integration & Dashboard

### 5.1 Unified Academy Dashboard (UI)
- [ ] Tab "Academy" mit Unter-Tabs:
  - **Agenten** — Karteibuch, Karriere, Badges
  - **Training** — Drills, Curricula, Fortschritt
  - **Evolution** — Prompt-History, A/B-Tests
  - **Analytics** — Ensemble-Diversity, Scout-Korrelationen
- [ ] Scout-Avatar-System (generierte Icons basierend auf Archetyp)
- [ ] Level-Up-Animationen
- [ ] Leaderboards: Global, Per-Symbol, Per-Timeframe

### 5.2 API Consolidation
- [ ] `GET /academy/status` — Aktueller Trainings-Status
- [ ] `POST /academy/drill/start` — Manuellen Drill starten
- [ ] `POST /academy/train/start` — Training-Loop manuell starten
- [ ] `POST /academy/train/stop` — Training-Loop stoppen
- [ ] `GET /academy/drills/available` — Liste aller verfügbaren Drills
- [ ] `GET /academy/ab-tests` — Alle A/B-Tests
- [ ] `GET /academy/curriculum/{scout_name}` — Curriculum-Fortschritt

### 5.3 Persistence Layer
- [ ] `logs/agent_careers.jsonl` — Karriere-Einträge
- [ ] `logs/prompt_registry.json` — Prompt-Versionen
- [ ] `logs/ab_tests.jsonl` — A/B-Test-Ergebnisse
- [ ] `logs/drill_results.jsonl` — Drill-Ergebnisse
- [ ] SQLite-Tables (optional für schnelle Queries):
  - `agent_careers`, `drill_results`, `ab_tests`, `prompt_versions`

---
## Phase 6: Testing & QA
- [ ] Unit Tests für AgentRegistry
- [ ] Unit Tests für TrainingDrills
- [ ] Unit Tests für PromptEvolution
- [ ] Unit Tests für ABTesting
- [ ] Integration Test: Full Training Cycle
- [ ] Performance Test: 1000 Drills in <5 Minuten
- [ ] Regression Test: Live-Trading wird durch Training nicht beeinträchtigt

---
## Akzeptanzkriterien
- [ ] Jeder Scout hat eine sichtbare "Karriere-Seite" mit Timeline
- [ ] Badges werden automatisch vergeben und im UI angezeigt
- [ ] Nutzer kann manuell Drills starten und sofort Feedback sehen
- [ ] A/B-Tests laufen autonom und wählen Prompt-Winners
- [ ] Training-Loop läuft nachts ohne manuelle Eingriffe
- [ ] Prompt-Versionen sind nachvollziehbar (Diff, Performance pro Version)
- [ ] Scout-Accuracy steigt messbar nach 100+ Drills
- [ ] Ensemble-Diversity liegt im optimalen Bereich (60-80%)
- [ ] Kein Performance-Impact auf Live-Trading
- [ ] 350+ Tests grün

# AI Trading Jules Prompt Pack

Dieses Paket enthaelt Markdown-Dateien, die zusammen einen kompletten Arbeitsauftrag fuer Google Jules bilden.

Ziel: Jules soll einen umsetzbaren Projektplan fuer ein simulation-first KI-Trading-Ecosystem erstellen, das Kimi Swarm, GPT-5.5 und/oder Manus als Research-, Review- und Orchestrierungs-Agenten nutzt.

## Dateien

1. `01_jules_masterprompt.md`
   - Der vollstaendige Copy-Paste-Masterprompt fuer Jules.

2. `02_research_brief_input.md`
   - Verdichteter Research-Kontext auf Basis deiner Deep-Research-Analyse.
   - Wichtig: Die Modell- und Quellenclaims sind als Eingabeannahmen markiert und sollen von Jules verifiziert werden.

3. `03_sigma_m8_context.md`
   - Kontext zum bestehenden Sigma PineScript und dem neuen M8 Execution Quality Gate.

4. `04_agent_roles_and_boundaries.md`
   - Klare Rollen, Grenzen und erlaubte/verbotene Aktionen fuer Kimi Swarm, GPT-5.5 und Manus.

5. `05_json_schema_contracts.md`
   - JSON-Schema-Vertraege fuer AI-Signal-Review, Risk-Flags, Journal, Strategie-Hypothesen und Backtest-Zusammenfassungen.

6. `06_validation_and_risk_gates.md`
   - Konkrete Validierungsregeln, Reject-Gates und Simulationsanforderungen.

7. `07_jules_execution_checklist.md`
   - Schrittfolge, wie du Jules mit dem Paket arbeiten laesst.

## Empfohlene Nutzung

1. Oeffne `01_jules_masterprompt.md`.
2. Fuege den Inhalt in Jules ein.
3. Haenge die anderen Markdown-Dateien als Kontext an oder kopiere sie unter den Masterprompt.
4. Lass Jules zuerst nur den Plan erstellen.
5. Danach erst Code-/Repo-Tasks daraus ableiten.

## Harte Leitlinie

Keine AI darf direkt Live-Orders platzieren.

AI-Agenten duerfen:
- recherchieren
- klassifizieren
- Hypothesen erzeugen
- Backtests orchestrieren
- Journals analysieren
- Risiken markieren
- Code vorschlagen

Deterministische Systeme muessen:
- final entscheiden
- validieren
- simulieren
- ablehnen
- loggen
- ausfuehren


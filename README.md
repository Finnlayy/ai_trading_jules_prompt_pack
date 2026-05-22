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

## Lokale AI-API-Konfiguration

Der Python-AI-Layer kann per `.env` zwischen Moonshot/Kimi, OpenAI/ChatGPT und Google Gemini wechseln. Die Swarm-Logik bleibt gleich: Sentiment-Scout, Technical-Scout, Risk-Scout und ein Orchestrator.

1. Kopiere `.env.example` nach `.env`.
2. Setze `AI_PROVIDER` auf `moonshot`, `openai` oder `gemini`.
3. Trage nur den passenden echten Key in `.env` ein.

```env
AI_PROVIDER=moonshot
MOONSHOT_API_KEY=dein_moonshot_key
MOONSHOT_MODEL=kimi-k2.6
```

```env
AI_PROVIDER=openai
OPENAI_API_KEY=dein_openai_key
OPENAI_MODEL=gpt-5.2
```

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=dein_gemini_key
GEMINI_MODEL=gemini-2.5-pro
```

Die echte `.env` ist in `.gitignore` eingetragen und darf nicht committed werden.

## Broker-Modus

Standard ist reine Simulation:

```env
BROKER_MODE=simulation
```

Fuer deinen Pionex Relay Server kannst du den Broker so umschalten:

```env
BROKER_MODE=pionex_relay
PIONEX_RELAY_ENABLED=false
PIONEX_RELAY_URL=http://127.0.0.1:5000/webhook
PIONEX_SIGNAL_BOT_UUID=deine_pionex_signal_bot_uuid
PIONEX_RELAY_CONTRACTS=1
```

Solange `PIONEX_RELAY_ENABLED=false` bleibt, erzeugt der Broker nur einen Dry-Run-Payload und sendet nichts an den Relay. Echte Weiterleitung an Pionex erst mit `PIONEX_RELAY_ENABLED=true`.

Fuer native Pionex REST-Ausfuehrung (ohne externen Relay) nutze:

```env
BROKER_MODE=pionex_direct
PIONEX_DIRECT_ENABLED=true
PIONEX_DIRECT_LIVE_TRADING_ENABLED=false
PIONEX_API_KEY=dein_pionex_api_key
PIONEX_API_SECRET=dein_pionex_api_secret
PIONEX_ALLOWED_SYMBOLS=BTC_USDT,BTC_USDT_PERP,ETH_USDT,ETH_USDT_PERP
PIONEX_DIRECT_FUTURES_MODE=mode1
AI_FAILURE_POLICY=reject_live
```

Wichtig:
- `PIONEX_DIRECT_LIVE_TRADING_ENABLED=false` bedeutet Dry-Run, auch wenn API-Keys gesetzt sind.
- `intent` ist optional im Payload (`ENTRY`/`CLOSE`). Wenn nicht gesetzt, gilt `ENTRY`.
- `AI_FAILURE_POLICY=reject_live` blockiert live-faehige Orders, falls die AI-Layer als unavailable markiert wird.
- Kelly-Sizing ist standardmaessig Half-Kelly (`KELLY_DEPLOY_MODE=half`) mit Min/Max-Risiko-Caps aus `.env`.

## Deterministischer War Room

Die Order-Engine arbeitet wie ein War Room: AI darf Informationen markieren,
aber der deterministische Judge entscheidet ueber `GO`, `HOLD` oder `KILL`.

Payload-Felder fuer Order-Management:
- `order_command`: `GO`, `HOLD` oder `KILL`; `HOLD` und `KILL` blockieren neue Entries.
- `market_regime`: optionales Farblabel `GREEN`, `YELLOW`, `ORANGE` oder `RED`.
- `bar_confirmed`: muss fuer neue Entries `true` sein.
- `chop_index`: Werte ueber `WAR_ROOM_CHOP_STANDBY_THRESHOLD` fuehren zu Standby.
- `hurst_exponent` und `macro_event_risk`: markieren Orange-Risk und deckeln Risk auf `WAR_ROOM_ORANGE_MAX_RISK_PCT`.
- `drawdown_pct`: ab `WAR_ROOM_HARD_KILL_DRAWDOWN_PCT` werden neue Entries hart blockiert.
- `pending_order_age_seconds`: zu alte Shadow-/Pending-Orders werden als expired geblockt.

AI-Regeln:
- AI darf keine Risk-Gates umgehen, keine Live-Order erzwingen und keine direkte Execution anfordern.
- AI mit Confidence unter `WAR_ROOM_AI_MIN_CONFIDENCE` blockiert live-faehige Entry-Pfade.
- `CLOSE` bleibt priorisiert, damit Risikoabbau nicht durch Entry-Gates blockiert wird.
- Full-Kelly aus Research-/War-Room-Metaphern ist kein Live-Default; produktiv bleibt Half-Kelly capped.

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

## Offline Research Layer

Die zusaetzlichen Fundstuecke werden als kuratierter Research- und Test-Korpus
gefuehrt, nicht als direkte Produktionsabhaengigkeit.

Konkret gilt:
- `app/research/reference_corpus.py` dokumentiert pro Quelle, ob sie uebernommen,
  offline adaptiert oder ausgeschlossen wird.
- `app/research/binance_futures_data.py` bereitet Binance USD-M Futures-Klines
  fuer Offline-Experimente vor. Der Live-Broker importiert dieses Modul nicht.
- Quellen mit synthetischen Daten, leeren Inhalten oder Wallet-/Private-Key-Material
  werden aus Training, Logs und Produktionspfaden ausgeschlossen.
- Invarianten aus alten Pionex/Pine-Testideen werden als secret-freie pytest-Tests
  gepflegt, ohne harte lokale Pfade, UUIDs oder echte Credentials.

Offline-Download mit optionalem MTF/CISD-Report:

```bash
python -m app.research.binance_futures_data \
  --symbol ETHUSDT \
  --interval 5m \
  --bars 1000 \
  --out app/scripts/data_cache/ETHUSDT_5m_research.csv \
  --mtf-report app/scripts/optimizer_results/ETHUSDT_5m_mtf_cisd.json \
  --mtf-timeframes 15,60,240
```

Die MTF/CISD-Auswertung resampled echte OHLCV-Buckets und nutzt fuer
Lower-Timeframe-Zeilen nur den vorherigen abgeschlossenen Higher-Timeframe-State.
Damit bleibt die Research-Schicht lookahead-sicher und getrennt vom Pionex Direct Broker.

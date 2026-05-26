# Jules Master Prompt: WebUI Redesign für MetricFlow Trading Bot

## Kontext

Du bist Jules, ein UI/UX-Design- und Frontend-Entwicklungs-Agent für den **MetricFlow Bot** — einen Multi-Agent KI-Trading-Bot mit:
- 4 AI Scouts (Technical, Sentiment, Risk, Macro)
- Paper Trading & Live Execution
- Confidence Registry (per-Symbol Scout-Learning)
- Autonomous Trading Loop
- Real-time Position Monitoring

**Tech Stack:** FastAPI Backend + Single-File React SPA (`frontend.html`, Babel Standalone, kein Build-Step)

**Aktuelle URL:** `http://localhost:8000/`

---

## Problem: Aktuelles UI ist nicht intuitiv

### Beobachtete UX-Probleme

1. **Kein Dashboard-First Design**
   - User landet auf einem unstrukturierten Gesichtsfeld
   - Keine sofortige Übersicht über Portfolio, offene Positionen, PnL
   - Tabs sind unlogisch gruppiert

2. **Tab-Navigation verwirrend**
   - "Overview" zeigt nichts Übersichtliches
   - "Control" vs "Live Paper" vs "Orders" — Zuständigkeit unklar
   - Keine visuelle Hierarchie (alles gleich wichtig dargestellt)

3. **Daten-Dichte zu hoch / zu niedrig**
   - KPI-Karten sind klein und unbedeutend
   - Tabellen (Watchlist, Orders, Positions) verschwenden Platz
   - Charts fehlen oder sind versteckt

4. **Keine Echtzeit-Visualisierung**
   - Keine Live-Preisanzeige für Watchlist-Symbole
   - Keine PnL-Visualisierung für offene Positionen
   - SSE-Events kommen an, aber visuelles Feedback fehlt

5. **Action-Buttons nicht prominent**
   - "Emergency Stop", "Start Loop" zu klein / versteckt
   - Keine Quick-Actions für häufige Tasks
   - Watchlist "Add"-Button hat kein visuelles Feedback

6. **Farb- & Typografie-Chaos**
   - `var(--ink)` löst nicht in allen Browsern auf → unsichtbarer Text
   - 12-Farben-Palette wird nicht konsistent angewendet
   - Keine klare Semantik: was ist ein Button, was ein Link, was ein Status?

---

## Ziel: Intuitive Trading-Dashboard-Erfahrung

### Design-Prinzipien

1. **Dashboard First**
   - Beim Öffnen sofort sehen: Portfolio-Wert, offene Positionen, heutiger PnL, aktiver Loop-Status
   - Alles auf einen Blick — wie TradingView, Bloomberg Terminal, oder CoinMarketCap

2. **Hierarchie durch Größe und Position**
   - Große KPIs oben (Portfolio, PnL, Winrate)
   - Mittlere Panels (Watchlist mit Live-Preisen, Open Positions)
   - Kleine Details unten (Logs, Konfiguration)

3. **Echtzeit-First**
   - Jede Zahl, die sich ändern kann, muss animiert aktualisieren (grüne/rote Pulse)
   - Preise in Watchlist live updaten
   - Positionen zeigen aktuellen Unrealized-PnL in Echtzeit

4. **One-Click Actions**
   - Emergency Stop = großer roter Button, immer sichtbar
   - Loop Start/Stop = Toggle-Switch statt kleiner Buttons
   - Add to Watchlist = Inline-Formular mit sofortigem Feedback

5. **Mobile-Responsive**
   - Aktuell bricht das Layout bei kleinen Bildschirmen
   - Trading-Apps werden oft auf Tablets/Handys genutzt

---

## Konkrete Aufgaben für Jules

### Phase 1: Dashboard-Struktur (Layout)

- [ ] **Hero-Section oben** (volle Breite):
  - Portfolio Value (gesamt)
  - Heutiger Realized PnL
  - Heutiger Unrealized PnL
  - Aktive Positionen (Count)
  - Loop Status (Running/Stopped/Paused) mit Farbe
  - Letztes Signal (wann, welches Symbol, Richtung, Ergebnis)

- [ ] **Hauptbereich 2-Spalten**:
  - **Linke Spalte (60%)**: Watchlist mit Live-Preisen + Mini-Chart-Sparklines
  - **Rechte Spalte (40%)**: Open Positions mit PnL-Bar-Charts

- [ ] **Unterer Bereich**:
  - Tabs für: AI Scout Detail | Confidence Registry | Trade History | System Logs

### Phase 2: Komponenten-Redesign

- [ ] **Watchlist-Karte** (pro Symbol):
  - Symbol-Name groß
  - Aktueller Preis (live, animiert)
  - 24h Change % mit Farbe
  - Mini Sparkline (letzte 20 Preispunkte)
  - Aktiv/Inaktiv Toggle
  - Remove-Button (nur Icon, nicht "Remove"-Text)

- [ ] **Open Position-Karte** (pro Position):
  - Symbol + Direction (LONG/SHORT) mit Farbe
  - Entry Price → Current Price (Pfeil-Visualisierung)
  - Size
  - Unrealized PnL als horizontaler Balken (grün/rot)
  - % Distance to Stop / Target
  - Time in Trade als Countdown-Visualisierung

- [ ] **KPI-Karten**:
  - Deutlich größer
  - Icon + Wert + Caption
  - Trend-Pfeil (↑/↓) vs gestern
  - Hintergrundfarbe basierend auf Wert (grün = gut, rot = schlecht)

### Phase 3: Interaktion & Feedback

- [ ] **Toast-Notifications** statt nur Log-Einträge:
  - "Signal generiert: BTCUSDT LONG @ 50000"
  - "Position geschlossen: TAKE_PROFIT +3.2%"
  - "Emergency Stop aktiviert"

- [ ] **Animationen**:
  - Preis-Änderungen: kurzer grüner/roter Glow
  - Neue Position: Slide-in von rechts
  - Closed Position: Slide-out nach links + PnL-Float

- [ ] **Loading-States**:
  - Skeleton-Screens statt leerer Tabellen
  - Spinner auf Buttons beim API-Call

### Phase 4: Farb- & Typografie-Fix

- [ ] **CSS-Variablen konsolidieren**:
  - Max. 6 Farben statt 12
  - Klare Semantik: Primary, Success, Warning, Danger, Info, Neutral
  - KEINE browser-abhängigen Variablen für Text — immer hardcoded Fallback

- [ ] **Typografie-System**:
  - H1: 32px bold (Seiten-Titel)
  - H2: 24px bold (Panel-Titel)
  - H3: 18px semibold (Karten-Titel)
  - Body: 14px regular
  - Caption: 12px medium
  - Mono: 13px (für Preise, Zahlen)

- [ ] **Dark Mode als Default**:
  - Trading-Interfaces sind traditionell dunkel
  - Bessere Lesbarkeit für lange Sessions
  - Weniger Augenbelastung

---

## Tools & Techniken

### Erlaubte Tools
- **HTML/CSS/JavaScript** direkt in `frontend.html`
- **React 18** (via Babel Standalone)
- **Inline SVG** für Icons und Sparklines
- **CSS Grid & Flexbox** für Layout
- **CSS Animations/Transitions** für Feedback
- **Canvas API** (optional für komplexe Charts)

### Verboten
- Keine externen Build-Tools (Webpack, Vite, etc.)
- Keine externen UI-Libraries (Material-UI, Ant Design, etc.)
- Keine externen Chart-Libraries (Chart.js, D3, etc.) — alles selbst bauen oder SVG
- Kein TypeScript

### Design-Referenzen
- **TradingView** — für Chart- und Watchlist-Layout
- **CoinMarketCap Portfolio** — für KPI-Darstellung
- **Bloomberg Terminal** — für Informationsdichte
- **Linear App** — für Dark Mode und saubere Typografie

---

## Output-Format

Jede Änderung an `frontend.html` muss:
1. **Vollständig sein** — keine halben Features
2. **Getestet sein** — im Browser öffnen, prüfen, Screenshots machen
3. **Dokumentiert sein** — kurze Notiz was geändert wurde und warum
4. **Nur eine Datei** — alles in `frontend.html`, keine neuen Dateien

---

## Akzeptanzkriterien

- [ ] Ein neuer User versteht nach 10 Sekunden was der Bot macht
- [ ] Alle aktiven Positionen sind auf einen Blick sichtbar
- [ ] Watchlist zeigt Live-Preise (oder zumindest zuletzt bekannte Preise)
- [ ] Loop Start/Stop ist sofort auffindbar und bedienbar
- [ ] Kein unsichtbarer Text in Tabellen
- [ ] Mobile Ansicht ist nutzbar (keine überlappenden Elemente)
- [ ] Dark Mode ist aktiv oder zumindest vorbereitet

---

## Startpunkt

Öffne `frontend.html` und analysiere die aktuelle Struktur. Beginne mit **Phase 1: Dashboard-Struktur** — dem Layout-Refactoring. Das ist der größte Hebel für intuitives UX.

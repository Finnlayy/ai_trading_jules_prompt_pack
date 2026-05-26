# Pionex Layout Editor — Reverse Engineering & Implementierungsplan

## Quelle
Screenshot der Pionex Web-Trading-Oberfläche (de.trading.pionex.com)

## Was Pionex macht

### Layout-Struktur
```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER: Logo | Spot ▼ | Futures ▼ | RWA ▼ | Markets | Earn ▼ | ...    │
├─────────────────────────────────────────────────────────────────────────┤
│  SIDEBAR    │  MAIN CONTENT AREA                          │  RIGHT     │
│  (Markets)  │                                             │  SETTINGS  │
│             │  ┌─────────────────────────────────────┐   │  PANEL     │
│  BTC/USDT   │  │ HEADER: Symbol | Price | 24h Change│   │            │
│  ETH/USDT   │  ├─────────────────────────────────────┤   │  Layout    │
│  HYPE/USDT  │  │  CHART (TradingView)                │   │  Settings  │
│  ...        │  │                                     │   │  ───────── │
│             │  └─────────────────────────────────────┘   │  Reset     │
│  PAIR/VOL   │  ┌─────────────────────────────────────┐   │  Lock      │
│  PRICE      │  │  ORDER/PORTFOLIO TABS               │   │  ───────── │
│  24H        │  │                                     │   │  Trading   │
│             │  └─────────────────────────────────────┘   │  Mode:     │
│             │                                             │  [L] [R]   │
│             │                                             │  ───────── │
│             │                                             │  ☑ Order   │
│             │                                             │  ☑ Market  │
│             │                                             │  ☑ K-Line  │
│             │                                             │  ☐ Quick   │
│             │                                             │  ...       │
└─────────────┴─────────────────────────────────────────────┴────────────┘
```

### Layout Settings Panel (Rechte Seite)

| Feature | Beschreibung |
|---------|-------------|
| **Reset to default** | Button — Layout auf Standard zurücksetzen |
| **Lock Current Layout** | Toggle — Verhindert versehentliches Verschieben |
| **Trading Mode** | Radio: Left (Sidebar links) / Right (Sidebar rechts) |
| **Panel Toggles** | Jeder Bereich einzeln ein-/ausschaltbar |

### Panel-Liste (aus Screenshot)
1. Order Book ☑
2. Market Trades ☐
3. Markets ☑
4. K-Line Bar ☑
5. Quick Market Bar ☐
6. Order List Bar ☑
7. Order Placement Bar ☑
8. Account ☐

## Reverse-Engineering: Wie es technisch funktioniert

### 1. State-Management
```javascript
// React State für Layout-Konfiguration
const [layout, setLayout] = useState({
  mode: "left",           // "left" | "right"
  locked: false,
  panels: {
    orderBook: true,
    marketTrades: false,
    markets: true,
    klineBar: true,
    quickMarketBar: false,
    orderListBar: true,
    orderPlacementBar: true,
    account: false,
  }
});
```

### 2. CSS Grid für Hauptlayout
```css
.trading-layout {
  display: grid;
  grid-template-columns: 280px 1fr 320px;  /* Sidebar | Main | Settings */
  grid-template-rows: auto 1fr;
  gap: 0;
  height: 100vh;
}

.trading-layout.right-mode {
  grid-template-columns: 1fr 280px 320px;  /* Main | Sidebar | Settings */
}

.trading-layout.no-markets {
  grid-template-columns: 1fr 320px;         /* Main | Settings */
}
```

### 3. Panel-Visibility
```css
.panel {
  transition: all 0.3s ease;
}

.panel.hidden {
  display: none;
}

.panel.collapsed {
  width: 0;
  overflow: hidden;
  opacity: 0;
}
```

### 4. Persistence
```javascript
// localStorage Key
const LAYOUT_KEY = "pionex_layout_v1";

// Load
const saved = localStorage.getItem(LAYOUT_KEY);
if (saved) setLayout(JSON.parse(saved));

// Save
useEffect(() => {
  localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
}, [layout]);
```

## Implementierungsplan für MetricFlow Bot

### Phase 1: Layout-State & Grid-System

**Neue State-Struktur in App-Component:**
```javascript
const [layoutConfig, setLayoutConfig] = useState(() => {
  const saved = localStorage.getItem("metricflow_layout");
  return saved ? JSON.parse(saved) : {
    mode: "left",
    locked: false,
    panels: {
      watchlist: true,
      chart: true,
      scoutDetail: true,
      positions: true,
      performance: true,
      aiLayer: false,
      confidence: false,
      logs: false,
    }
  };
});
```

**CSS Grid für Hauptlayout:**
```css
.metricflow-layout {
  display: grid;
  grid-template-areas:
    "sidebar header header"
    "sidebar main settings";
  grid-template-columns: 260px 1fr 280px;
  grid-template-rows: auto 1fr;
  height: 100vh;
  overflow: hidden;
}

.metricflow-layout.right-mode {
  grid-template-areas:
    "header header sidebar"
    "settings main sidebar";
}

.metricflow-layout.no-watchlist {
  grid-template-columns: 1fr 280px;
  grid-template-areas:
    "header settings"
    "main settings";
}
```

### Phase 2: Layout Settings Panel

**Komponente: `LayoutSettingsPanel`**
```jsx
function LayoutSettingsPanel({ layout, onChange }) {
  return (
    <div className="layout-settings">
      <div className="settings-header">
        <h3>Layout Settings</h3>
      </div>
      
      <button onClick={() => onChange(resetLayout())}>
        Reset to Default
      </button>
      
      <Toggle 
        label="Lock Current Layout"
        value={layout.locked}
        onChange={v => onChange({...layout, locked: v})}
      />
      
      <div className="trading-mode">
        <label>Trading Mode</label>
        <div className="mode-selector">
          <button 
            className={layout.mode === "left" ? "active" : ""}
            onClick={() => onChange({...layout, mode: "left"})}
          >
            <Icon name="layout-left" />
            Left
          </button>
          <button 
            className={layout.mode === "right" ? "active" : ""}
            onClick={() => onChange({...layout, mode: "right"})}
          >
            <Icon name="layout-right" />
            Right
          </button>
        </div>
      </div>
      
      <div className="panel-toggles">
        <label>Panels</label>
        {Object.entries(layout.panels).map(([key, value]) => (
          <Toggle
            key={key}
            label={formatLabel(key)}
            value={value}
            onChange={v => onChange({
              ...layout,
              panels: {...layout.panels, [key]: v}
            })}
          />
        ))}
      </div>
    </div>
  );
}
```

### Phase 3: Toggle Switch Component

```jsx
function Toggle({ label, value, onChange }) {
  return (
    <label className="toggle-switch">
      <span className="toggle-label">{label}</span>
      <div className={`toggle-track ${value ? "on" : "off"}`} onClick={() => onChange(!value)}>
        <div className="toggle-thumb" />
      </div>
    </label>
  );
}
```

```css
.toggle-switch {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  cursor: pointer;
}

.toggle-track {
  width: 40px;
  height: 22px;
  border-radius: 11px;
  background: var(--line);
  position: relative;
  transition: background 0.2s;
}

.toggle-track.on {
  background: var(--emerald);
}

.toggle-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.toggle-track.on .toggle-thumb {
  transform: translateX(18px);
}
```

### Phase 4: Panel-System

**Jedes Panel wird eine conditionally-rendered Komponente:**

```jsx
// Im Haupt-Layout:
<div className={`metricflow-layout ${layout.mode}-mode`}>
  {layout.panels.watchlist && (
    <aside className="panel-watchlist">
      <WatchlistPanel ... />
    </aside>
  )}
  
  <main className="panel-main">
    {layout.panels.chart && <ChartPanel ... />}
    {layout.panels.scoutDetail && <ScoutDetailPanel ... />}
    {layout.panels.positions && <PositionsPanel ... />}
    {layout.panels.performance && <PerformancePanel ... />}
  </main>
  
  <aside className="panel-settings">
    <LayoutSettingsPanel layout={layout} onChange={setLayout} />
  </aside>
</div>
```

## Vorteile dieses Ansatzes

| Vorteil | Beschreibung |
|---------|-------------|
| **Einfach** | Keine externe Lib, kein Drag&Drop |
| **Schnell** | CSS Grid = native Performance |
| **Persistent** | localStorage merkt User-Präferenz |
| **Responsive** | Grid-Areas können umgebrochen werden |
| **Erweiterbar** | Neue Panels = neuer Toggle |

## Dateien zu ändern

- `frontend.html` — Alles in einer Datei
  - Neue State: `layoutConfig`
  - Neue Komponente: `LayoutSettingsPanel`
  - Neue Komponente: `Toggle`
  - Refactored Layout: CSS Grid statt fixe Spalten
  - Persistence: localStorage in `useEffect`

## Konkrete Next Steps für Jules

1. **Grid-Layout bauen** — `metricflow-layout` mit CSS Grid
2. **LayoutSettingsPanel** — Rechte Sidebar mit Toggles
3. **Persistence** — localStorage load/save
4. **Default-Layout definieren** — Welche Panels sind standardmäßig an?
5. **Responsive Fallback** — Auf Mobile nur 1 Spalte

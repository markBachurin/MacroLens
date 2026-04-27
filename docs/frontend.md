# MacroLens — Frontend

## Overview

The dashboard is a multi-page vanilla JS application served by Django. No build step, no framework, no npm. Chart.js 4.4.1 handles all visualizations. ES6 modules (`type="module"`) structure the code across pages without a bundler.

The dashboard consumes the REST API exclusively — it has no direct database access.

---

## Technology Stack

| Concern | Choice | Reason |
|---|---|---|
| Charts | Chart.js 4.4.1 (CDN) | Rich interactive charts with no build toolchain |
| Zoom / Pan | chartjs-plugin-zoom 2.0.1 + hammer.js 2.0.8 (CDN) | Ctrl+scroll zoom and drag pan on time series |
| Modules | ES6 native `type="module"` | Code organization without bundler |
| Templates | Django template engine | Served by same Django app as the API |
| CSS | Single flat `dashboard.css` | No preprocessor needed at this scale |

---

## Directory Structure

```
dashboard/
├── static/
│   ├── css/
│   │   └── dashboard.css           ← All styles: layout, cards, tables, gauges
│   └── js/
│       ├── api.js                  ← Centralized API client
│       ├── chartUtils.js           ← Shared Chart.js config and utilities
│       ├── components/
│       │   └── anomalyTimeline.js  ← Reusable z-score multi-series chart
│       └── pages/
│           ├── home.js
│           ├── anomalies.js
│           ├── correlations.js
│           ├── macro.js
│           ├── regression.js
│           ├── lags.js
│           └── stress.js
└── templates/dashboard/
    ├── base.html
    ├── home.html
    ├── anomalies.html
    ├── correlations.html
    ├── factors.html
    ├── regression.html
    ├── lags.html
    └── stress.html
```

---

## Pages

| Page | Route | JS Module | API Calls |
|---|---|---|---|
| Current Regime | `/dashboard/` | `pages/home.js` | snapshot, anomalies, correlations, series detail (yield spread), regression latest |
| Anomaly Monitor | `/dashboard/anomalies/` | `pages/anomalies.js` | snapshot, anomalies, zscore history (8 series) |
| Correlations | `/dashboard/correlations/` | `pages/correlations.js` | correlations (all 3 windows), correlation pair |
| Macro Factors | `/dashboard/factors/` | `pages/macro.js` | series detail (WTI, real WTI, yield spread, S&P 500) |
| Regression | `/dashboard/regression/` | `pages/regression.js` | regression latest, regression history |
| Lag Analysis | `/dashboard/lags/` | `pages/lags.js` | lag results |
| Fear & Greed | `/dashboard/stress/` | `pages/stress.js` | zscore history (6 series), snapshot |

---

## Shared Modules

### `api.js` — API Client

Single source of truth for all fetch calls. Exports one function per endpoint.

```js
const API_BASE = 'http://localhost:8000/api';

async function apiFetch(path) { ... }   // throws on non-ok

export async function fetchSnapshot()
export async function fetchSeriesList()
export async function fetchSeriesDetail(seriesId, limit = 9999, offset = 0)
export async function fetchCorrelations(window = 90)
export async function fetchCorrelationPair(seriesA, seriesB, window = 90)
export async function fetchRegressionLatest()
export async function fetchRegressionHistory()
export async function fetchAnomalies()
export async function fetchLagResults()
export async function fetchZscoreHistory(seriesIds)  // parallel fetches, returns { id: { date: zscore } }
```

### `chartUtils.js` — Shared Utilities

Imported by every page module. Exports:

| Export | Type | Description |
|---|---|---|
| `TOOLTIP` | object | Standard Chart.js tooltip style preset |
| `COLORS` | string[] | 9-color palette for multi-series charts |
| `rColor(r)` | function | Pearson r [-1,+1] → RGB string for heatmap cells |
| `textOnBg(r)` | function | Returns `#fff` or `#16213E` based on heatmap background |
| `fmtVal(v, seriesId)` | function | Formats a value with per-series logic (index vs decimal) |
| `sig(p)` | function | p-value → significance stars (`***`, `**`, `*`, `""`) |
| `SERIES_LABELS` | object | Maps raw `series_id` strings to human-readable labels |
| `label(seriesId)` | function | Looks up `SERIES_LABELS`, falls back to raw id |
| `CORRELATION_PAIRS` | array | The 9 canonical pairs used in correlations and lags |
| `startClock(elementId)` | function | Renders a live UTC clock into a DOM element |
| `activateWindowBtn(btn, cb)` | function | Manages active state on window-selector buttons |
| `makeChart(instance, canvasId, config)` | function | Destroys existing chart instance before creating new one |
| `sliceDates(dates, days)` | function | Slices a sorted date array to the last N entries |
| `zoomPanConfig()` | function | Returns chartjs-plugin-zoom config (Ctrl+scroll zoom, drag pan) |
| `setChartWindow(chart, allDates, days)` | function | Zooms chart to last N entries using `zoomScale` on category axis |

### `components/anomalyTimeline.js` — Z-Score Timeline

Reusable multi-series z-score chart with zoom/pan. Used on both Home and Anomaly Monitor pages.

```js
export async function initAnomalyTimeline(canvasId, opts = {})
// opts.series  — array of { id, color } (defaults to 6 key series)
// opts.window  — initial visible window in trading days (default 1260 = 5Y)
// returns { chart, allDates, setWindow(days) }
```

Draws ±2.5σ threshold lines. Fetches zscore history via `fetchZscoreHistory`. Calls `setChartWindow` after creation to initialize the visible range.

---

## Page Details

### `home.js` — Current Regime

Loaded on `/dashboard/`. Orchestrates 6 parallel data loads on init, then refreshes stat cards every 60 seconds.

**Sections:**
- **Stat cards** — 6 key series (S&P 500, NASDAQ, WTI, Gold, Fed Funds, 10Y). Each shows current value, z-score, and anomaly chip. Color-coded by z-score severity.
- **Anomaly Cluster Timeline** — `initAnomalyTimeline` component. Window selector: 1Y / 5Y / MAX.
- **Active Anomalies mini-table** — fetches `/api/anomalies/`, shows series, z-score, date.
- **Correlation Snapshot** — mini heatmap table of latest 90-day r for all 9 pairs.
- **Yield Curve Spread mini-chart** — line chart of `DERIVED_YIELD_SPREAD` with zero-line and fill coloring (green above / red below).
- **Regression Betas** — table of latest beta, p-value, VIF for WTI, Fed Funds, 10Y. R² displayed below.
- **Z-Score Gauges** — horizontal gauge bar for every series, sorted by |z-score| descending. Thresholds at ±2.5σ marked.

### `correlations.js` — Correlations

**Sections:**
- **Full heatmap table** — 9 pairs × 3 windows (30D / 90D / 252D) side by side. Each cell color-coded by `rColor`. Clicking a cell selects that pair. Trend column shows whether |r| is strengthening or weakening (30D vs 252D).
- **Rolling correlation time series** — line chart of r over time for selected pair. ±0.3 reference lines.
- **Pair detail panel** — table of r, p-value, significance for all 3 windows. Auto-generated economic interpretation text based on the pair and current regime.

### `regression.js` — Regression

**Sections:**
- **Latest coefficients table** — beta, p-value, significance stars, VIF for each of the 3 independent variables. VIF color-coded (green < 2, amber 2–5, red > 5).
- **Beta evolution chart** — rolling beta_wti, beta_fed, beta_t10y over time. Zoom/pan enabled.
- **R² over time chart** — separate chart. Zoom/pan enabled.
- **R² insight text** — auto-generated interpretation of explanatory power.

### `lags.js` — Lag Analysis

**Sections:**
- **Pair selector dropdown** — choose from the 9 canonical pairs.
- **Bar chart** — Pearson r at each lag (1d, 5d, 10d, 20d, 60d). Bars faded if p > 0.05.
- **Interpretation text** — auto-generated text: strongest lag, significance, economic meaning.
- **Full results table** — all pairs × all lags, sorted by |r| descending.

### `anomalies.js` — Anomaly Monitor

**Sections:**
- **Anomaly table** — series flagged in last 14 days with value, z-score, HIGH/LOW direction chip.
- **Z-Score Gauges** — same as Home page.
- **Anomaly Timeline** — `initAnomalyTimeline` component with series toggle buttons.
- **Stress Index chart** — mean |z-score| across 6 key series over time. Threshold line at 2.5.

### `macro.js` — Macro Factors

**Sections:**
- **Nominal vs Real WTI chart** — dual-line: nominal WTI in USD and CPI-adjusted real WTI. Zoom/pan enabled.
- **Yield curve spread + S&P 500 chart** — dual y-axis: spread (%) on left, S&P 500 on right. Red fill when spread < 0 (inversion). Inversion count displayed.

### `stress.js` — Fear & Greed

**Sections:**
- **Current stress banner** — large stress index value with LOW / ELEVATED / EXTREME label and color.
- **Per-series z-score readouts** — current z-score for VIX, WTI, Gold, Fed Funds, 10Y, S&P 500.
- **Stress Index time series** — mean |z-score| over time. Reference lines at 1.5 and 2.5.
- **Component breakdown chart** — individual z-score per series over time on one chart.

---

## Template Structure

`base.html` provides:
- Navigation bar with links to all 7 pages. Active state via `{% block nav_* %}active{% endblock %}`.
- Chart.js, hammer.js, chartjs-plugin-zoom loaded from CDN.
- Live UTC clock via `startClock('clock')` imported from `chartUtils.js`.
- `{% block content %}` and `{% block scripts %}` for page content and page-specific JS.

Each page template extends `base.html`, defines content, and loads its page module as `<script type="module">`.

---

## Interaction Patterns

**Window selectors** — buttons labeled 1Y / 5Y / MAX (or 30D / 90D / 252D). Call `setChartWindow` or re-fetch with new `?window=` param. Active button tracked via CSS class.

**Zoom / Pan** — enabled on all time series charts. Ctrl+scroll to zoom, drag to pan. Reset zoom available via double-click (default Chart.js zoom plugin behavior).

**Auto-refresh** — stat cards on Home page refresh every 60 seconds via `setInterval`. No other pages auto-refresh.

**Series toggles** — Anomaly Monitor page has toggle buttons to show/hide individual series on the timeline chart.

---

## Key Design Decisions

**No React / No build step** — Chart.js in vanilla JS with ES6 modules achieves all required interactivity. Avoids Node.js, npm, webpack, and a separate dev server. The dashboard is a demonstration vehicle; engineering effort belongs in the pipeline, not the UI.

**ES6 modules without bundler** — `type="module"` scripts handle imports natively in modern browsers. This means `api.js` and `chartUtils.js` are imported by page scripts directly, with no build step needed.

**Centralized API client** — all fetch calls go through `api.js`. One place to change `API_BASE` when deploying. Errors surface uniformly via the `apiFetch` wrapper.

**`makeChart` pattern** — every chart creation goes through `makeChart(existingInstance, canvasId, config)` which destroys the old instance before creating a new one. Prevents memory leaks and canvas reuse errors when the user changes selections.

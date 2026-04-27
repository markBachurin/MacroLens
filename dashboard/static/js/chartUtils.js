/* ═══════════════════════════════════════════════════════════════
   chartUtils.js — MacroLens shared Chart.js configuration
   Import this on every page before any chart is created.
   ═══════════════════════════════════════════════════════════════ */

/* ── GLOBAL CHART.JS DEFAULTS ────────────────────────────────── */
Chart.defaults.font.family = "'IBM Plex Sans', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.color = '#8896A7';
Chart.defaults.borderColor = '#DDE3EA';

/* ── TOOLTIP PRESET ──────────────────────────────────────────── */
export const TOOLTIP = {
  backgroundColor: '#16213E',
  titleColor: '#fff',
  bodyColor: 'rgba(255,255,255,0.8)',
  padding: 10,
  cornerRadius: 4,
  displayColors: true,
  boxWidth: 10,
  boxHeight: 10,
};

/* ── CHART PALETTE ───────────────────────────────────────────── */
export const COLORS = [
  '#0073BB', // blue
  '#1D8348', // green
  '#D68910', // amber
  '#8E44AD', // purple
  '#C0392B', // red
  '#5D6D7E', // slate
  '#16A085', // teal
  '#E67E22', // orange
  '#2C3E50', // dark
];

/* ── HEATMAP COLOR SCALE ─────────────────────────────────────── */
/**
 * Maps Pearson r [-1, +1] → RGB color
 * -1 = blue (#2166AC), 0 = white, +1 = red (#C0392B)
 * @param {number|null} r
 * @returns {string} CSS rgb() string
 */
export function rColor(r) {
  if (r === null || r === undefined) return '#F4F6F8';
  const t = (r + 1) / 2; // normalize to [0,1]
  const neg = [33, 102, 172];
  const mid = [247, 247, 247];
  const pos = [192, 57, 43];
  const lerp = (a, b, t) => Math.round(a + (b - a) * t);
  let R, G, B;
  if (t < 0.5) {
    const u = t * 2;
    R = lerp(neg[0], mid[0], u);
    G = lerp(neg[1], mid[1], u);
    B = lerp(neg[2], mid[2], u);
  } else {
    const u = (t - 0.5) * 2;
    R = lerp(mid[0], pos[0], u);
    G = lerp(mid[1], pos[1], u);
    B = lerp(mid[2], pos[2], u);
  }
  return `rgb(${R},${G},${B})`;
}

/**
 * Returns black or white text color depending on heatmap background
 * @param {number|null} r
 * @returns {string}
 */
export function textOnBg(r) {
  return (r !== null && Math.abs(r) > 0.4) ? '#fff' : '#16213E';
}

/* ── VALUE FORMATTERS ────────────────────────────────────────── */
/**
 * Format a series value for display, with per-series logic
 * @param {number|null} v
 * @param {string} seriesId
 * @returns {string}
 */
export function fmtVal(v, seriesId = '') {
  if (v === null || v === undefined) return '—';
  if (seriesId.includes('GSPC') || seriesId.includes('IXIC') || seriesId === 'GC=F') {
    return v.toLocaleString('en', { maximumFractionDigits: 0 });
  }
  return v.toFixed(2);
}

/**
 * Statistical significance stars
 * @param {number} p
 * @returns {string}
 */
export function sig(p) {
  if (p < 0.001) return '***';
  if (p < 0.01)  return '**';
  if (p < 0.05)  return '*';
  return '';
}

/* ── SERIES LABELS ───────────────────────────────────────────── */
export const SERIES_LABELS = {
  'DCOILWTICO':          'WTI Oil',
  'DCOILBRENTEU':        'Brent',
  'GC=F':                'Gold',
  '^GSPC':               'S&P 500',
  '^IXIC':               'NASDAQ',
  '^VIX':                'VIX',
  'DGS10':               '10Y Yield',
  'FEDFUNDS':            'Fed Funds',
  'BC_2YEAR':            '2Y Yield',
  'BC_10YEAR':           '10Y (Treasury)',
  'CPIAUCSL':            'CPI',
  'EUR/USD':             'EUR/USD',
  'DERIVED_YIELD_SPREAD':'Yield Spread',
  'DERIVED_REAL_WTI':    'Real WTI',
  'DERIVED_WTI_SP500':   'WTI/SP500',
};

export function label(seriesId) {
  return SERIES_LABELS[seriesId] || seriesId;
}

/* ── CORRELATION PAIRS ───────────────────────────────────────── */
export const CORRELATION_PAIRS = [
  ['DCOILWTICO', '^GSPC'],
  ['DCOILWTICO', 'GC=F'],
  ['DCOILWTICO', 'CPIAUCSL'],
  ['FEDFUNDS',   '^GSPC'],
  ['FEDFUNDS',   'GC=F'],
  ['DGS10',      '^GSPC'],
  ['DGS10',      'DCOILWTICO'],
  ['^GSPC',      '^IXIC'],
  ['^VIX',       '^GSPC'],
];

/* ── CLOCK ───────────────────────────────────────────────────── */
export function startClock(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const tick = () => {
    const now = new Date();
    el.textContent = now.toUTCString().slice(17, 22) + ' UTC';
  };
  tick();
  setInterval(tick, 1000);
}

/* ── WINDOW BUTTON HELPER ────────────────────────────────────── */
/**
 * Activate one button in a group and call callback
 * @param {HTMLElement} btn - the clicked button
 * @param {Function} callback
 */
export function activateWindowBtn(btn, callback) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  callback();
}

/* ── DESTROY AND RECREATE CHART ──────────────────────────────── */
/**
 * Safely destroy an existing chart instance before creating a new one
 * @param {Chart|null} instance
 * @param {string} canvasId
 * @param {object} config
 * @returns {Chart}
 */
export function makeChart(instance, canvasId, config) {
  if (instance) instance.destroy();
  return new Chart(document.getElementById(canvasId), config);
}

/* ── SLICE DATES BY WINDOW ───────────────────────────────────── */
/**
 * Slice a sorted date array to the last N entries
 * @param {string[]} dates - sorted ascending
 * @param {number} days - trading days to keep (9999 = all)
 * @returns {string[]}
 */
export function sliceDates(dates, days) {
  if (days >= dates.length) return dates;
  return dates.slice(-days);
}


/* ── ZOOM / PAN CONFIG ───────────────────────────────────────── */
/**
 * Returns Chart.js zoom plugin config for x-axis pan + scroll zoom.
 */
export function zoomPanConfig() {
  return {
    pan: {
      enabled: true,
      mode: 'x',
      threshold: 5,
    },
    zoom: {
      wheel: {
        enabled: true,
        modifierKey: 'ctrl',
      },
      pinch: { enabled: true },
      mode: 'x',
    },
    limits: {
      x: { minRange: 30 },
    },
  };
}

/**
 * Set visible x-axis range to last N trading days from the end of the dataset.
 * Uses chart.zoomScale with numeric index range on category axis.
 * @param {Chart} chart - Chart.js instance
 * @param {string[]} allDates - full sorted date array (YYYY-MM-DD)
 * @param {number} days - trading days to show (99999 = all)
 */
export function setChartWindow(chart, allDates, days) {
  if (!chart || !allDates.length) return;
  const total = allDates.length;
  const start = days >= total ? 0 : total - days;
  const end   = total - 1;
  // Reset first, then zoom to range by index
  chart.resetZoom();
  if (days < total) {
    chart.zoomScale('x', { min: start, max: end }, 'default');
  }
}
/* ═══════════════════════════════════════════════════════════════
   pages/macro.js — Real vs Nominal Oil + Yield Curve Spread
   ═══════════════════════════════════════════════════════════════ */

import { fetchSeriesDetail } from '../api.js';
import { TOOLTIP, zoomPanConfig, setChartWindow } from '../chartUtils.js';

let oilChart_   = null;
let yieldChart_ = null;
let nominalDates = [], nominalValues = [];
let realDates    = [], realValues    = [];
let spreadDates  = [], spreadValues  = [];
let sp500Dates   = [], sp500Values   = [];

/* ── OIL ─────────────────────────────────────────────────────── */
async function loadOilData() {
  const [nominal, real] = await Promise.all([
    fetchSeriesDetail('DCOILWTICO'),
    fetchSeriesDetail('DERIVED_REAL_WTI'),
  ]);
  const nomSorted  = [...nominal].reverse();
  const realSorted = [...real].reverse();
  nominalDates  = nomSorted.map(d => d.date);
  nominalValues = nomSorted.map(d => d.value);
  realDates     = realSorted.map(d => d.date);
  realValues    = realSorted.map(d => d.value);
}

function renderOil(initDays = 99999) {
  if (oilChart_) oilChart_.destroy();
  oilChart_ = new Chart(document.getElementById('oilChart'), {
    type: 'line',
    data: {
      labels: nominalDates,
      datasets: [
        { label: 'Nominal WTI (USD)', data: nominalValues, borderColor: '#0073BB', borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true },
        { label: 'Real WTI (CPI-adjusted)', data: realValues, borderColor: '#D68910', borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false, borderDash: [4,2], spanGaps: true },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, padding: 16, usePointStyle: true } },
        tooltip: { ...TOOLTIP, callbacks: { label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y?.toFixed(2) ?? 'n/a'}` } },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: { title: { display: true, text: 'USD per barrel' }, ticks: { callback: v => `$${v}` } },
      },
      animation: { duration: 200 },
    },
  });

  setChartWindow(oilChart_, nominalDates, initDays);

  const latestNom  = nominalValues.filter(v => v !== null).at(-1);
  const latestReal = realValues.filter(v => v !== null).at(-1);
  document.getElementById('oil-insight').innerHTML = latestNom
    ? `Current nominal WTI: <strong>$${latestNom.toFixed(2)}</strong> · Real (CPI-adjusted): <strong>$${latestReal?.toFixed(2) ?? '—'}</strong>. The gap between the lines represents the <strong>inflation effect</strong>. The 2022 spike was less extreme than it appeared once inflation is stripped out.`
    : '';
}

window.setOilWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  setChartWindow(oilChart_, nominalDates, days);
};

/* ── YIELD CURVE ─────────────────────────────────────────────── */
async function loadYieldData() {
  const [spread, sp500] = await Promise.all([
    fetchSeriesDetail('DERIVED_YIELD_SPREAD'),
    fetchSeriesDetail('^GSPC'),
  ]);
  const spreadSorted = [...spread].reverse();
  const sp500Sorted  = [...sp500].reverse();
  spreadDates  = spreadSorted.map(d => d.date);
  spreadValues = spreadSorted.map(d => d.value);
  sp500Dates   = sp500Sorted.map(d => d.date);
  sp500Values  = sp500Sorted.map(d => d.value);
}

function renderYield(initDays = 99999) {
  const sp500Map = {};
  sp500Dates.forEach((d, i) => { sp500Map[d] = sp500Values[i]; });

  const posData = spreadValues.map(v => v >= 0 ? v : 0);
  const negData = spreadValues.map(v => v <  0 ? v : 0);
  const spData  = spreadDates.map(d => sp500Map[d] ?? null);

  if (yieldChart_) yieldChart_.destroy();
  yieldChart_ = new Chart(document.getElementById('yieldChart'), {
    type: 'line',
    data: {
      labels: spreadDates,
      datasets: [
        { label: 'Yield Spread (left)', data: spreadValues, borderColor: '#0073BB', borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false, yAxisID: 'ySpread', spanGaps: true },
        { label: '_pos', data: posData, borderColor: 'transparent', backgroundColor: 'rgba(29,131,72,0.08)', borderWidth: 0, pointRadius: 0, fill: 'origin', yAxisID: 'ySpread' },
        { label: '_neg', data: negData, borderColor: 'transparent', backgroundColor: 'rgba(192,57,43,0.18)', borderWidth: 0, pointRadius: 0, fill: 'origin', yAxisID: 'ySpread' },
        { label: '0', data: spreadDates.map(() => 0), borderColor: 'rgba(0,0,0,0.2)', borderWidth: 1, borderDash: [3,3], pointRadius: 0, fill: false, yAxisID: 'ySpread' },
        { label: 'S&P 500 (right)', data: spData, borderColor: '#1D8348', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: false, yAxisID: 'ySP500', borderDash: [6,2], spanGaps: true },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP,
          filter: item => !item.dataset.label.startsWith('_') && item.dataset.label !== '0',
          callbacks: {
            label: ctx => {
              if (ctx.dataset.label === 'Yield Spread (left)') return `Spread: ${ctx.parsed.y?.toFixed(2)}%`;
              if (ctx.dataset.label === 'S&P 500 (right)') return `S&P 500: ${ctx.parsed.y?.toLocaleString('en', {maximumFractionDigits:0})}`;
              return null;
            },
          },
        },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        ySpread: { type: 'linear', position: 'left', title: { display: true, text: 'Spread (%)' }, ticks: { callback: v => `${v.toFixed(1)}%` }, grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,0.25)' : '#DDE3EA' } },
        ySP500:  { type: 'linear', position: 'right', title: { display: true, text: 'S&P 500' }, grid: { drawOnChartArea: false }, ticks: { callback: v => v.toLocaleString('en', {maximumFractionDigits:0}) } },
      },
      animation: { duration: 200 },
    },
  });

  setChartWindow(yieldChart_, spreadDates, initDays);

  const currentSpread = spreadValues.filter(v => v !== null).at(-1);
  const isInverted    = currentSpread < 0;
  const inversions    = [];
  let inStart = null;
  spreadDates.forEach((d, i) => {
    if (spreadValues[i] < 0 && inStart === null) inStart = d;
    if (spreadValues[i] >= 0 && inStart !== null) { inversions.push(inStart); inStart = null; }
  });
  if (inStart) inversions.push(inStart);

  document.getElementById('yield-insight').innerHTML = `
    Current spread: <strong style="color:${isInverted ? 'var(--negative)' : 'var(--positive)'}">${currentSpread?.toFixed(2) ?? '—'}%</strong> — 
    ${isInverted ? '<strong style="color:var(--negative)">Yield curve is inverted.</strong> Historically a reliable recession indicator within 12–18 months.' : 'Yield curve is not inverted. Normal term structure.'}
    ${inversions.length ? ` Detected <strong>${inversions.length}</strong> inversion period${inversions.length > 1 ? 's' : ''} in full history.` : ''}`;
}

window.setYieldWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  setChartWindow(yieldChart_, spreadDates, days);
};

/* ── INIT ────────────────────────────────────────────────────── */
async function init() {
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';
  await Promise.all([loadOilData(), loadYieldData()]);
  renderOil(99999);
  renderYield(99999);
}

init();
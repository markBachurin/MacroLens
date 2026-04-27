/* ═══════════════════════════════════════════════════════════════
   pages/stress.js — Fear & Greed Index with zoom/pan
   ═══════════════════════════════════════════════════════════════ */

import { fetchZscoreHistory, fetchSnapshot } from '../api.js';
import { TOOLTIP, zoomPanConfig, setChartWindow, label } from '../chartUtils.js';

const STRESS_SERIES = [
  { id: '^VIX',       color: '#C0392B', elId: 'z-vix'   },
  { id: 'DCOILWTICO', color: '#0073BB', elId: 'z-wti'   },
  { id: 'GC=F',       color: '#D68910', elId: 'z-gold'  },
  { id: 'FEDFUNDS',   color: '#5D6D7E', elId: 'z-fed'   },
  { id: 'DGS10',      color: '#8E44AD', elId: 'z-t10y'  },
  { id: '^GSPC',      color: '#1D8348', elId: 'z-sp500' },
];

let stressChart_    = null;
let componentChart_ = null;
let zData           = {};
let allDates        = [];
let stressByDate    = {};

function buildStressIndex() {
  const byDate = {};
  STRESS_SERIES.forEach(s => {
    Object.entries(zData[s.id] || {}).forEach(([date, z]) => {
      if (z === null) return;
      if (!byDate[date]) byDate[date] = [];
      byDate[date].push(Math.abs(z));
    });
  });
  allDates     = Object.keys(byDate).sort();
  stressByDate = {};
  allDates.forEach(d => {
    const arr = byDate[d];
    stressByDate[d] = arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
  });
}

async function loadBanner() {
  const snap = await fetchSnapshot();
  const get  = id => snap.find(d => d.series_id === id)?.zscore_252d ?? null;

  STRESS_SERIES.forEach(s => {
    const z  = get(s.id);
    const el = document.getElementById(s.elId);
    if (!el) return;
    el.textContent = z !== null ? `${z.toFixed(2)}σ` : '—';
    el.style.color = Math.abs(z) > 2.5 ? 'var(--negative)' : Math.abs(z) > 1.5 ? 'var(--warning)' : 'var(--positive)';
  });

  const zValues = STRESS_SERIES.map(s => get(s.id)).filter(z => z !== null);
  const current = zValues.length ? zValues.reduce((a, b) => a + Math.abs(b), 0) / zValues.length : null;
  const valEl   = document.getElementById('stress-value');
  const labelEl = document.getElementById('stress-label');
  const banner  = document.getElementById('stress-banner');

  if (current !== null) {
    valEl.textContent = current.toFixed(2);
    if (current > 2.5) {
      valEl.style.color = 'var(--negative)';
      labelEl.textContent = 'EXTREME STRESS — Multiple series simultaneously outside historical norms';
      banner.style.borderTopColor = 'var(--negative)';
    } else if (current > 1.5) {
      valEl.style.color = 'var(--warning)';
      labelEl.textContent = 'ELEVATED STRESS — Some macro series outside normal ranges';
      banner.style.borderTopColor = 'var(--warning)';
    } else {
      valEl.style.color = 'var(--positive)';
      labelEl.textContent = 'LOW STRESS — Markets within normal historical ranges';
      banner.style.borderTopColor = 'var(--positive)';
    }
  }
}

function renderStress(initDays = 1260) {
  const values = allDates.map(d => stressByDate[d] ?? null);
  const latest = values.filter(v => v !== null).at(-1);

  if (stressChart_) stressChart_.destroy();
  stressChart_ = new Chart(document.getElementById('stressChart'), {
    type: 'line',
    data: {
      labels: allDates,
      datasets: [
        { label: 'Stress Index', data: values, borderColor: '#C0392B', backgroundColor: 'rgba(192,57,43,0.08)', borderWidth: 2, pointRadius: 0, tension: 0.3, fill: 'origin', spanGaps: true },
        { label: '2.5', data: allDates.map(() => 2.5), borderColor: 'rgba(192,57,43,0.4)', borderWidth: 1, borderDash: [5,4], pointRadius: 0, fill: false },
        { label: '1.5', data: allDates.map(() => 1.5), borderColor: 'rgba(214,137,16,0.4)', borderWidth: 1, borderDash: [3,3], pointRadius: 0, fill: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { ...TOOLTIP, callbacks: { label: ctx => ctx.dataset.label === 'Stress Index' ? `Stress: ${ctx.parsed.y?.toFixed(2)}` : null } },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: { min: 0, title: { display: true, text: 'Mean |z-score|' } },
      },
      animation: { duration: 200 },
    },
  });

  setChartWindow(stressChart_, allDates, initDays);

  document.getElementById('stress-insight').innerHTML = latest !== null
    ? `Current stress index: <strong>${latest.toFixed(2)}</strong>. ${latest > 2.5 ? 'Consistent with major macro shock events — COVID March 2020 peaked near 4.0, Ukraine war Feb 2022 peaked near 3.5.' : latest > 1.5 ? 'Moderately elevated. Some macro series outside typical range.' : 'Within normal bounds. Key series within ~1.5σ of rolling means.'}`
    : '';
}

window.setWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  setChartWindow(stressChart_, allDates, days);
};

function renderComponents(initDays = 1260) {
  const datasets = STRESS_SERIES.map(s => ({
    label:           label(s.id),
    data:            allDates.map(d => zData[s.id]?.[d] ?? null),
    borderColor:     s.color,
    backgroundColor: 'transparent',
    borderWidth:     1.5,
    pointRadius:     0,
    tension:         0.2,
    spanGaps:        true,
  }));

  datasets.push({ label: '+2.5σ', data: allDates.map(() =>  2.5), borderColor: 'rgba(192,57,43,0.35)', borderWidth: 1, borderDash: [5,4], pointRadius: 0, fill: false });
  datasets.push({ label: '−2.5σ', data: allDates.map(() => -2.5), borderColor: 'rgba(192,57,43,0.35)', borderWidth: 1, borderDash: [5,4], pointRadius: 0, fill: false });

  if (componentChart_) componentChart_.destroy();
  componentChart_ = new Chart(document.getElementById('componentChart'), {
    type: 'line',
    data: { labels: allDates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10, padding: 12, usePointStyle: true } },
        tooltip: { ...TOOLTIP, callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2) ?? 'n/a'}σ` } },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: { min: -6, max: 6, title: { display: true, text: 'Z-score (252d)' }, grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,0.2)' : '#DDE3EA' } },
      },
      animation: { duration: 200 },
    },
  });

  setChartWindow(componentChart_, allDates, initDays);
}

window.setComponentWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  setChartWindow(componentChart_, allDates, days);
};

async function init() {
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';

  [zData] = await Promise.all([
    fetchZscoreHistory(STRESS_SERIES.map(s => s.id)),
    loadBanner(),
  ]);

  buildStressIndex();
  renderStress(1260);
  renderComponents(1260);
}

init();
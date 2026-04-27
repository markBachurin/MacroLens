/* ═══════════════════════════════════════════════════════════════
   pages/regression.js — OLS Beta Evolution with zoom/pan
   ═══════════════════════════════════════════════════════════════ */

import { fetchRegressionLatest, fetchRegressionHistory } from '../api.js';
import { TOOLTIP, zoomPanConfig, setChartWindow, sig } from '../chartUtils.js';

let betaChart_ = null;
let r2Chart_   = null;
let betaDates  = [];
let r2Dates    = [];

async function loadLatest() {
  const d = await fetchRegressionLatest();
  document.getElementById('reg-date').textContent   = `As of ${d.date}`;
  document.getElementById('r2-display').textContent = d.r_squared?.toFixed(4) ?? '—';

  const vars = [
    { name: 'WTI Return',  beta: d.beta_wti,  p: d.p_value_wti,  vif: d.vif_wti  },
    { name: 'Fed Funds Δ', beta: d.beta_fed,  p: d.p_value_fed,  vif: d.vif_fed  },
    { name: '10Y Yield Δ', beta: d.beta_t10y, p: d.p_value_t10y, vif: d.vif_t10y },
  ];

  document.getElementById('reg-tbody').innerHTML = vars.map(v => `
    <tr>
      <td><strong>${v.name}</strong></td>
      <td class="mono" style="color:${v.beta > 0 ? 'var(--positive)' : 'var(--negative)'};font-weight:600">${v.beta?.toFixed(4) ?? '—'}</td>
      <td class="mono">${v.p?.toFixed(4) ?? '—'}</td>
      <td style="color:var(--blue-primary);font-weight:600">${sig(v.p) || '—'}</td>
      <td class="mono" style="color:${v.vif > 5 ? 'var(--negative)' : v.vif > 2 ? 'var(--warning)' : 'var(--positive)'}">${v.vif?.toFixed(2) ?? '—'}</td>
    </tr>`).join('');

  const r2 = d.r_squared;
  document.getElementById('r2-insight').innerHTML = r2 !== null
    ? `R² = <strong>${r2.toFixed(4)}</strong> — these 3 factors explain <strong>${(r2*100).toFixed(1)}%</strong> of S&P 500 daily return variance. ${r2 < 0.1 ? 'Low explanatory power is expected for daily equity returns.' : r2 < 0.25 ? 'Moderate explanatory power — macro factors influencing equities.' : 'High explanatory power — macro regime strongly driving returns.'}`
    : '';
}

async function loadHistory() {
  const history = await fetchRegressionHistory();
  betaDates = history.map(d => d.date);
  r2Dates   = history.map(d => d.date);

  const betaWti = history.map(d => d.beta_wti);
  const betaFed = history.map(d => d.beta_fed);
  const betaT10 = history.map(d => d.beta_t10y);
  const r2vals  = history.map(d => d.r_squared);

  if (betaChart_) betaChart_.destroy();
  betaChart_ = new Chart(document.getElementById('betaChart'), {
    type: 'line',
    data: {
      labels: betaDates,
      datasets: [
        { label: 'β WTI',       data: betaWti, borderColor: '#0073BB', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true },
        { label: 'β Fed Funds', data: betaFed, borderColor: '#D68910', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true },
        { label: 'β 10Y Yield', data: betaT10, borderColor: '#8E44AD', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true },
        { label: '0', data: betaDates.map(() => 0), borderColor: 'rgba(0,0,0,0.15)', borderWidth: 1, borderDash: [4,4], pointRadius: 0, fill: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10, padding: 14, usePointStyle: true } },
        tooltip: { ...TOOLTIP, callbacks: { label: ctx => ctx.dataset.label === '0' ? null : `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(4)}` } },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
        y: { title: { display: true, text: 'β coefficient' }, grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,0.2)' : '#DDE3EA' } },
      },
      animation: { duration: 200 },
    },
  });

  if (r2Chart_) r2Chart_.destroy();
  r2Chart_ = new Chart(document.getElementById('r2Chart'), {
    type: 'line',
    data: {
      labels: r2Dates,
      datasets: [{ label: 'R²', data: r2vals, borderColor: '#1D8348', backgroundColor: 'rgba(29,131,72,0.08)', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: 'origin', spanGaps: true }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { ...TOOLTIP, callbacks: { label: ctx => `R²: ${ctx.parsed.y?.toFixed(4)}` } },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
        y: { min: 0, max: 1, title: { display: true, text: 'R²' } },
      },
      animation: { duration: 200 },
    },
  });
}

async function init() {
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';
  await Promise.all([loadLatest(), loadHistory()]);
}

init();
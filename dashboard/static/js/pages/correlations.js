/* ═══════════════════════════════════════════════════════════════
   pages/correlations.js — Correlation Heatmap + Rolling TS
   ═══════════════════════════════════════════════════════════════ */

import { fetchCorrelations, fetchCorrelationPair } from '../api.js';
import { TOOLTIP, CORRELATION_PAIRS, label, rColor, makeChart, sig, zoomPanConfig, setChartWindow } from '../chartUtils.js';

/* ── STATE ───────────────────────────────────────────────────── */
let heatmapWindow = 30;
let corrTsWindow  = 30;
let selectedPair  = CORRELATION_PAIRS[0]; // default: WTI ↔ SP500
let corrTsChart   = null;

/* ── HEATMAP ─────────────────────────────────────────────────── */
async function renderHeatmap() {
  const data   = await fetchCorrelations(heatmapWindow);
  const byPair = {};
  data.forEach(d => { byPair[`${d.series_a}|${d.series_b}`] = d; });

  // Build 9-row × 1-col table (one row per pair, showing r value for selected window)
  // We show all 3 windows side by side always — more useful than one at a time
  const [w30, w90, w252] = await Promise.all([
    fetchCorrelations(30),
    fetchCorrelations(90),
    fetchCorrelations(252),
  ]);

  const byW = { 30: {}, 90: {}, 252: {} };
  w30.forEach(d  => { byW[30][`${d.series_a}|${d.series_b}`]  = d; });
  w90.forEach(d  => { byW[90][`${d.series_a}|${d.series_b}`]  = d; });
  w252.forEach(d => { byW[252][`${d.series_a}|${d.series_b}`] = d; });

  const el = document.getElementById('full-heatmap');
  el.innerHTML = `
    <table class="heatmap-table" style="width:100%">
      <thead>
        <tr>
          <th class="row-label">Pair</th>
          <th style="text-align:center; width:100px">30D</th>
          <th style="text-align:center; width:100px">90D</th>
          <th style="text-align:center; width:100px">252D</th>
          <th style="text-align:left; padding-left:16px; color:var(--text-muted); font-size:10px">Trend</th>
        </tr>
      </thead>
      <tbody>
        ${CORRELATION_PAIRS.map(([a, b]) => {
          const key  = `${a}|${b}`;
          const rkey = `${b}|${a}`;
          const get  = (w) => {
            const d = byW[w][key] || byW[w][rkey];
            return d?.pearson_r ?? null;
          };
          const r30  = get(30);
          const r90  = get(90);
          const r252 = get(252);

          const cell = (r, w) => {
            if (r === null) return `<td class="heatmap-cell empty">—</td>`;
            const bg = rColor(r);
            const tc = Math.abs(r) > 0.4 ? '#fff' : '#16213E';
            return `
              <td class="heatmap-cell"
                style="background:${bg}; color:${tc}; cursor:pointer"
                onclick="selectPair('${a}', '${b}')"
                title="${label(a)} ↔ ${label(b)} (${w}D): r = ${r.toFixed(3)}">
                ${r.toFixed(2)}
              </td>`;
          };

          // Trend arrow: compare 30D vs 252D
          const trend = (r30 !== null && r252 !== null)
            ? (Math.abs(r30) > Math.abs(r252) ? '↑ strengthening' : '↓ weakening')
            : '—';
          const trendColor = trend.includes('↑') ? 'var(--positive)' : trend === '—' ? 'var(--text-muted)' : 'var(--negative)';
          const isSelected = selectedPair[0] === a && selectedPair[1] === b;

          return `
            <tr style="${isSelected ? 'background:var(--blue-light);' : ''}">
              <th class="row-label" style="font-weight:500; color:var(--text-secondary)">
                ${label(a)} ↔ ${label(b)}
              </th>
              ${cell(r30, 30)}
              ${cell(r90, 90)}
              ${cell(r252, 252)}
              <td style="padding-left:16px; font-size:11px; color:${trendColor}; white-space:nowrap">
                ${trend}
              </td>
            </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

/* ── PAIR SELECTOR ───────────────────────────────────────────── */
function buildPairSelect() {
  const sel = document.getElementById('pair-select');
  sel.innerHTML = CORRELATION_PAIRS.map(([a, b]) =>
    `<option value="${a}|${b}">${label(a)} ↔ ${label(b)}</option>`
  ).join('');
  sel.value = `${selectedPair[0]}|${selectedPair[1]}`;
}

window.onPairChange = function() {
  const [a, b] = document.getElementById('pair-select').value.split('|');
  selectedPair = [a, b];
  renderHeatmap(); // re-highlight selected row
  loadCorrTs();
  loadPairDetail();
};

window.selectPair = function(a, b) {
  selectedPair = [a, b];
  document.getElementById('pair-select').value = `${a}|${b}`;
  renderHeatmap();
  loadCorrTs();
  loadPairDetail();
};

window.setHeatmapWindow = function(w, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  heatmapWindow = w;
  renderHeatmap();
};

/* ── ROLLING CORRELATION TIME SERIES ─────────────────────────── */
async function loadCorrTs() {
  const [a, b] = selectedPair;
  const data   = await fetchCorrelationPair(a, b, corrTsWindow);

  document.getElementById('corr-ts-title').textContent =
    `Rolling Correlation — ${label(a)} ↔ ${label(b)}`;

  const dates  = data.map(d => d.date);
  const values = data.map(d => d.pearson_r);

  corrTsChart = makeChart(corrTsChart, 'corrTsChart', {
    type: 'line',
    data: {
      labels: dates,
      datasets: [
        {
          label: 'Pearson r',
          data: values,
          borderColor: '#0073BB',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
          fill: 'origin',
          backgroundColor: ctx => {
            const v = ctx.raw;
            return v >  0.3 ? 'rgba(29,131,72,0.12)'
                 : v < -0.3 ? 'rgba(192,57,43,0.12)'
                 : 'rgba(93,109,126,0.07)';
          },
        },
        {
          label: '+0.3', data: dates.map(() => 0.3),
          borderColor: 'rgba(29,131,72,0.3)', borderWidth: 1,
          borderDash: [4, 4], pointRadius: 0, fill: false,
        },
        {
          label: '0', data: dates.map(() => 0),
          borderColor: 'rgba(0,0,0,0.15)', borderWidth: 1,
          borderDash: [2, 2], pointRadius: 0, fill: false,
        },
        {
          label: '−0.3', data: dates.map(() => -0.3),
          borderColor: 'rgba(192,57,43,0.3)', borderWidth: 1,
          borderDash: [4, 4], pointRadius: 0, fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP,
          callbacks: {
            label: ctx => `r: ${ctx.parsed.y?.toFixed(3) ?? 'n/a'}`,
          },
        },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8 } },
        y: {
          min: -1, max: 1,
          title: { display: true, text: 'Pearson r' },
          grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,0.2)' : '#DDE3EA' },
        },
      },
      animation: { duration: 200 },
    },
  });
}

window.setCorrTsWindow = function(w, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  corrTsWindow = w;
  loadCorrTs();
};

/* ── PAIR DETAIL PANEL ───────────────────────────────────────── */
async function loadPairDetail() {
  const [a, b] = selectedPair;

  document.getElementById('pair-detail-title').textContent =
    `${label(a)} ↔ ${label(b)}`;

  const [w30, w90, w252] = await Promise.all([
    fetchCorrelations(30),
    fetchCorrelations(90),
    fetchCorrelations(252),
  ]);

  const getR = (data) => {
    const key  = `${a}|${b}`;
    const rkey = `${b}|${a}`;
    return data.find(d =>
      `${d.series_a}|${d.series_b}` === key ||
      `${d.series_a}|${d.series_b}` === rkey
    );
  };

  const d30  = getR(w30);
  const d90  = getR(w90);
  const d252 = getR(w252);

  const row = (label_, d) => {
    if (!d) return `<tr><td><strong>${label_}</strong></td><td colspan="4" style="color:var(--text-muted)">—</td></tr>`;
    const r   = d.pearson_r;
    const str = Math.abs(r) > 0.5 ? 'Strong' : Math.abs(r) > 0.3 ? 'Moderate' : 'Weak';
    const dir = r > 0 ? 'Positive' : 'Negative';
    return `
      <tr>
        <td><strong>${label_}</strong></td>
        <td class="mono" style="color:${r > 0 ? 'var(--positive)' : 'var(--negative)'}; font-weight:600">
          ${r.toFixed(3)}
        </td>
        <td class="mono">${d.p_value?.toFixed(4) ?? '—'}</td>
        <td>${sig(d.p_value)}</td>
        <td><span class="chip ${Math.abs(r) > 0.3 ? (r > 0 ? 'normal' : 'anomaly') : 'neutral'}">${dir} ${str}</span></td>
      </tr>`;
  };

  // Generate insight text
  const r90val = d90?.pearson_r;
  const insight = r90val !== null && r90val !== undefined
    ? generateInsight(a, b, r90val)
    : 'No data available for this pair.';

  document.getElementById('pair-detail-body').innerHTML = `
    <table class="data-table" style="margin-bottom:14px">
      <thead><tr><th>Window</th><th>Pearson r</th><th>P-Value</th><th>Sig</th><th>Strength</th></tr></thead>
      <tbody>
        ${row('30D', d30)}
        ${row('90D', d90)}
        ${row('252D', d252)}
      </tbody>
    </table>
    <div class="insight-box">${insight}</div>`;
}

function generateInsight(a, b, r) {
  const regime = r > 0.3 ? 'positive correlation regime'
               : r < -0.3 ? 'negative correlation regime'
               : 'near-zero (decoupled) regime';

  let implication = '';
  if (a === 'DCOILWTICO' && b === '^GSPC') {
    implication = r < -0.3
      ? 'Oil acting as an equity headwind — consistent with stagflation.'
      : r > 0.3 ? 'Risk-on environment — oil and equities moving together.'
      : 'Decoupled — oil and equities responding to different drivers.';
  } else if (a === '^VIX' && b === '^GSPC') {
    implication = 'VIX and SP500 are structurally inversely correlated. Strong negative r confirms data integrity.';
  } else if (a === '^GSPC' && b === '^IXIC') {
    implication = 'SP500 and NASDAQ near-perfect correlation confirms they move as one market.';
  } else if (a === 'DCOILWTICO' && b === 'CPIAUCSL') {
    implication = r > 0.3
      ? 'Oil price increases are feeding into inflation — energy-driven CPI pressure.'
      : 'Oil and CPI decoupled — inflation driven by non-energy factors.';
  } else if (a === 'FEDFUNDS') {
    implication = r < -0.3
      ? 'Rate hikes correlating with equity decline — tightening cycle in effect.'
      : 'Market has priced in rate path — limited additional sensitivity.';
  } else if (a === 'DGS10') {
    implication = r < -0.3
      ? 'Rising long yields pressuring equities — duration risk being repriced.'
      : 'Equities and yields moving together — growth-driven yield rise.';
  }

  return `Currently in <strong>${regime}</strong> (r = ${r.toFixed(2)}, 90D window). ${implication}`;
}

/* ── INIT ────────────────────────────────────────────────────── */
async function init() {
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';

  buildPairSelect();

  await renderHeatmap();
  await Promise.all([loadCorrTs(), loadPairDetail()]);
}

init();
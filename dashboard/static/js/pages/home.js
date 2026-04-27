/* ═══════════════════════════════════════════════════════════════
   pages/home.js — Current Regime dashboard orchestrator
   ═══════════════════════════════════════════════════════════════ */

import { fetchSnapshot, fetchAnomalies, fetchCorrelations, fetchSeriesDetail, fetchRegressionLatest } from '../api.js';
import { fmtVal, label, TOOLTIP, rColor, makeChart, CORRELATION_PAIRS } from '../chartUtils.js';
import { initAnomalyTimeline } from '../components/anomalyTimeline.js';

/* ── STAT CARDS ──────────────────────────────────────────────── */
const STAT_IDS = ['^GSPC', '^IXIC', 'DCOILWTICO', 'GC=F', 'FEDFUNDS', 'DGS10'];

async function loadStatCards() {
  const data = await fetchSnapshot();
  const row  = document.getElementById('stat-row');

  row.innerHTML = STAT_IDS.map(id => {
    const s      = data.find(d => d.series_id === id);
    if (!s) return '';
    const z      = s.zscore_252d?.toFixed(2) ?? 'n/a';
    const zNum   = s.zscore_252d ?? 0;
    const cls    = s.anomaly_flag ? 'is-anomaly' : Math.abs(zNum) > 1.5 ? 'is-warning' : '';
    const zColor = Math.abs(zNum) > 2.5 ? 'var(--negative)'
                 : Math.abs(zNum) > 1.5 ? 'var(--warning)'
                 : 'var(--text-muted)';
    return `
      <div class="stat-card ${cls}">
        <div class="stat-name">${label(id)}</div>
        <div class="stat-value">${fmtVal(s.value, id)}</div>
        <div class="stat-meta">
          <span class="stat-zscore" style="color:${zColor}">z: ${z}σ</span>
          ${s.anomaly_flag ? '<span class="chip anomaly"><span class="pulse-dot" style="width:6px;height:6px;margin-right:3px"></span>ANOMALY</span>' : ''}
        </div>
      </div>`;
  }).join('');

  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';
}

/* ── ANOMALY MINI TABLE ──────────────────────────────────────── */
async function loadAnomalyMini() {
  const data = await fetchAnomalies();
  const el   = document.getElementById('anomaly-mini');

  if (!data.length) {
    el.innerHTML = '<div style="padding:20px;color:var(--text-muted);text-align:center;font-size:13px">No active anomalies ✓</div>';
    return;
  }

  el.innerHTML = `
    <table class="data-table">
      <thead><tr><th></th><th>Series</th><th>Z-Score</th><th>Date</th></tr></thead>
      <tbody>
        ${data.map(d => `
          <tr>
            <td><span class="pulse-dot"></span></td>
            <td>${label(d.series_id)}</td>
            <td class="mono" style="color:${d.zscore_252d > 0 ? 'var(--negative)' : '#2166AC'}">
              ${d.zscore_252d?.toFixed(2) ?? '—'}σ
            </td>
            <td class="mono">${d.date}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

/* ── MINI HEATMAP ────────────────────────────────────────────── */
async function loadMiniHeatmap() {
  const data   = await fetchCorrelations(90);
  const byPair = {};
  data.forEach(d => { byPair[`${d.series_a}|${d.series_b}`] = d.pearson_r; });

  const el = document.getElementById('mini-heatmap');
  el.innerHTML = `
    <table style="border-collapse:collapse;width:100%">
      ${CORRELATION_PAIRS.map(([a, b]) => {
        const r  = byPair[`${a}|${b}`] ?? byPair[`${b}|${a}`] ?? null;
        const bg = rColor(r);
        const tc = r !== null && Math.abs(r) > 0.4 ? '#fff' : '#16213E';
        return `
          <tr>
            <td style="padding:4px 8px 4px 0;font-size:11px;color:var(--text-muted);white-space:nowrap">
              ${label(a)} ↔ ${label(b)}
            </td>
            <td style="background:${bg};color:${tc};padding:4px 10px;border-radius:3px;text-align:center;font-weight:600;min-width:56px;font-family:var(--mono);font-size:12px">
              ${r !== null ? r.toFixed(2) : '—'}
            </td>
          </tr>`;
      }).join('')}
    </table>`;
}

/* ── YIELD CURVE MINI CHART ──────────────────────────────────── */
let yieldChart = null;

async function loadYieldMini() {
  const raw    = await fetchSeriesDetail('DERIVED_YIELD_SPREAD');
  const sorted = [...raw].reverse(); // API returns newest-first
  const labels = sorted.map(d => d.date);
  const values = sorted.map(d => d.value);

  yieldChart = makeChart(yieldChart, 'yieldMiniChart', {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: '10Y−2Y',
          data: values,
          borderColor: '#0073BB',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
          fill: 'origin',
          backgroundColor: ctx => {
            const v = ctx.raw;
            return v < 0 ? 'rgba(192,57,43,0.15)' : 'rgba(29,131,72,0.08)';
          },
        },
        {
          label: '0',
          data: labels.map(() => 0),
          borderColor: 'rgba(0,0,0,0.2)',
          borderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: TOOLTIP },
      scales: {
        x: { ticks: { maxTicksLimit: 5 } },
        y: { title: { display: true, text: '%' } },
      },
    },
  });
}

/* ── REGRESSION BETA SUMMARY ─────────────────────────────────── */
async function loadBetaSummary() {
  const d = await fetchRegressionLatest();
  document.getElementById('beta-date').textContent = `As of ${d.date}`;

  const vars = [
    { name: 'WTI Return',  beta: d.beta_wti,  p: d.p_value_wti,  vif: d.vif_wti  },
    { name: 'Fed Funds Δ', beta: d.beta_fed,  p: d.p_value_fed,  vif: d.vif_fed  },
    { name: '10Y Yield Δ', beta: d.beta_t10y, p: d.p_value_t10y, vif: d.vif_t10y },
  ];

  document.getElementById('beta-summary').innerHTML = `
    <table class="data-table">
      <thead><tr><th>Variable</th><th>Beta</th><th>P-Val</th><th>VIF</th></tr></thead>
      <tbody>
        ${vars.map(v => `
          <tr>
            <td><strong>${v.name}</strong></td>
            <td class="mono" style="color:${v.beta > 0 ? 'var(--positive)' : 'var(--negative)'}">
              ${v.beta?.toFixed(4) ?? '—'}
            </td>
            <td class="mono">${v.p?.toFixed(4) ?? '—'}</td>
            <td class="mono" style="color:${v.vif > 5 ? 'var(--negative)' : v.vif > 2 ? 'var(--warning)' : 'var(--positive)'}">
              ${v.vif?.toFixed(2) ?? '—'}
            </td>
          </tr>`).join('')}
      </tbody>
    </table>
    <div style="padding:14px 16px;border-top:1px solid var(--border)">
      <span style="font-size:11px;color:var(--text-muted)">Model R²</span>
      <div class="mono" style="font-size:26px;font-weight:500;margin-top:2px">${d.r_squared?.toFixed(4) ?? '—'}</div>
    </div>`;
}

/* ── Z-SCORE GAUGES ──────────────────────────────────────────── */
async function loadGauges() {
  const data   = await fetchSnapshot();
  const sorted = [...data]
    .filter(d => d.zscore_252d !== null)
    .sort((a, b) => Math.abs(b.zscore_252d) - Math.abs(a.zscore_252d));

  document.getElementById('gauge-panel').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0 32px">
      ${sorted.map(d => {
        const z   = d.zscore_252d;
        const pct = Math.min(Math.abs(z) / 4 * 100, 100);
        const col = z >  2.5 ? 'var(--negative)'
                  : z < -2.5 ? '#2166AC'
                  : z >  1.5 ? 'var(--warning)'
                  : 'var(--blue-muted)';
        const left = z >= 0 ? '50%' : `${50 - pct / 2}%`;
        const w    = `${pct / 2}%`;
        return `
          <div class="gauge-row">
            <div class="gauge-name" title="${label(d.series_id)}">${label(d.series_id)}</div>
            <div class="gauge-bar-wrap">
              <div class="gauge-bar" style="left:${left};width:${w};background:${col}"></div>
              <div class="gauge-threshold" style="left:calc(50% + 50%*2.5/4)"></div>
              <div class="gauge-threshold" style="left:calc(50% - 50%*2.5/4)"></div>
            </div>
            <div class="gauge-val">${z.toFixed(2)}σ</div>
          </div>`;
      }).join('')}
    </div>`;
}

/* ── ANOMALY TIMELINE WINDOW CONTROL ─────────────────────────── */
let timeline = null;

window.setWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  timeline?.setWindow(days);
};

/* ── INIT ────────────────────────────────────────────────────── */
async function init() {
  await Promise.all([
    loadStatCards(),
    loadAnomalyMini(),
    loadMiniHeatmap(),
    loadYieldMini(),
    loadBetaSummary(),
    loadGauges(),
  ]);

  timeline = await initAnomalyTimeline('anomalyChart', { window: 1260 });

  // Refresh stat cards every 60s
  setInterval(loadStatCards, 60_000);
}

init();
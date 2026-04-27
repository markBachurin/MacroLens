/* ═══════════════════════════════════════════════════════════════
   pages/anomalies.js — Anomaly Monitor + Fear & Greed
   ═══════════════════════════════════════════════════════════════ */

import { fetchSnapshot, fetchAnomalies, fetchZscoreHistory } from '../api.js';
import { TOOLTIP, label, fmtVal, zoomPanConfig, setChartWindow } from '../chartUtils.js';
import { initAnomalyTimeline } from '../components/anomalyTimeline.js';

const ALL_SERIES = [
  { id: 'DCOILWTICO', color: '#0073BB' },
  { id: '^GSPC',      color: '#1D8348' },
  { id: '^VIX',       color: '#C0392B' },
  { id: 'GC=F',       color: '#D68910' },
  { id: 'DGS10',      color: '#8E44AD' },
  { id: 'FEDFUNDS',   color: '#5D6D7E' },
  { id: 'CPIAUCSL',   color: '#16A085' },
  { id: 'BC_2YEAR',   color: '#E67E22' },
];

let zData        = {};
let allDates     = [];
let activeIds    = new Set(ALL_SERIES.slice(0, 6).map(s => s.id));
let timelineObj  = null;
let stressChart_ = null;
let stressDates  = [];
let stressByDate = {};

/* ── TOGGLES ─────────────────────────────────────────────────── */
function buildToggles() {
  const container = document.getElementById('series-toggles');
  container.innerHTML = ALL_SERIES.map(s => `
    <button data-id="${s.id}"
      style="padding:4px 10px;font-size:11px;border-radius:12px;border:1.5px solid ${s.color};
             background:${activeIds.has(s.id) ? s.color : 'transparent'};
             color:${activeIds.has(s.id) ? '#fff' : s.color};
             cursor:pointer;font-family:var(--font);transition:all 0.15s;"
      onclick="toggleSeries('${s.id}','${s.color}',this)"
    >${label(s.id)}</button>
  `).join('');
}

window.toggleSeries = function(id, color, btn) {
  if (activeIds.has(id)) {
    if (activeIds.size <= 1) return;
    activeIds.delete(id);
    btn.style.background = 'transparent';
    btn.style.color      = color;
  } else {
    activeIds.add(id);
    btn.style.background = color;
    btn.style.color      = '#fff';
  }
  if (timelineObj?.chart) {
    timelineObj.chart.data.datasets.forEach((ds, i) => {
      const sid = ALL_SERIES[i]?.id;
      if (sid) ds.hidden = !activeIds.has(sid);
    });
    timelineObj.chart.update();
  }
};

window.setTimelineWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  timelineObj?.setWindow(days);
};

/* ── ANOMALY TABLE ───────────────────────────────────────────── */
async function loadAnomalyTable() {
  const data  = await fetchAnomalies();
  const tbody = document.getElementById('anomaly-tbody');
  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:24px">No active anomalies ✓</td></tr>`;
    return;
  }
  tbody.innerHTML = data.map(d => `
    <tr>
      <td><span class="pulse-dot"></span></td>
      <td><strong>${label(d.series_id)}</strong><br>
          <span style="font-size:11px;color:var(--text-muted);font-family:var(--mono)">${d.series_id}</span></td>
      <td class="mono">${fmtVal(d.value, d.series_id)}</td>
      <td class="mono" style="color:${d.zscore_252d > 0 ? 'var(--negative)' : '#2166AC'};font-weight:600">
        ${d.zscore_252d?.toFixed(2) ?? '—'}σ</td>
      <td><span class="chip ${d.zscore_252d > 0 ? 'anomaly' : 'info'}">${d.zscore_252d > 0 ? '⬆ HIGH' : '⬇ LOW'}</span></td>
      <td class="mono" style="color:var(--text-muted)">${d.date}</td>
    </tr>`).join('');
}

/* ── GAUGES ──────────────────────────────────────────────────── */
async function loadGauges() {
  const data   = await fetchSnapshot();
  const sorted = [...data].filter(d => d.zscore_252d !== null)
                          .sort((a, b) => Math.abs(b.zscore_252d) - Math.abs(a.zscore_252d));
  document.getElementById('gauge-panel').innerHTML = sorted.map(d => {
    const z   = d.zscore_252d;
    const pct = Math.min(Math.abs(z) / 4 * 100, 100);
    const col = z > 2.5 ? 'var(--negative)' : z < -2.5 ? '#2166AC' : z > 1.5 ? 'var(--warning)' : 'var(--blue-muted)';
    const left = z >= 0 ? '50%' : `${50 - pct / 2}%`;
    return `
      <div class="gauge-row">
        <div class="gauge-name" title="${label(d.series_id)}">${label(d.series_id)}</div>
        <div class="gauge-bar-wrap">
          <div class="gauge-bar" style="left:${left};width:${pct/2}%;background:${col}"></div>
          <div class="gauge-threshold" style="left:calc(50% + 50%*2.5/4)"></div>
          <div class="gauge-threshold" style="left:calc(50% - 50%*2.5/4)"></div>
        </div>
        <div class="gauge-val">${z.toFixed(2)}σ</div>
      </div>`;
  }).join('');
}

/* ── FEAR & GREED ────────────────────────────────────────────── */
const STRESS_IDS = ['^VIX', 'DCOILWTICO', 'GC=F', 'FEDFUNDS', 'DGS10', '^GSPC'];

function buildStressData() {
  const byDate = {};
  STRESS_IDS.forEach(id => {
    Object.entries(zData[id] || {}).forEach(([date, z]) => {
      if (z === null) return;
      if (!byDate[date]) byDate[date] = [];
      byDate[date].push(Math.abs(z));
    });
  });
  stressDates  = Object.keys(byDate).sort();
  stressByDate = {};
  stressDates.forEach(d => {
    const arr = byDate[d];
    stressByDate[d] = arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
  });
}

function renderStress(initDays = 1260) {
  const values = stressDates.map(d => stressByDate[d] ?? null);
  const latest = values.filter(v => v !== null).at(-1);

  if (stressChart_) stressChart_.destroy();
  stressChart_ = new Chart(document.getElementById('stressChart'), {
    type: 'line',
    data: {
      labels: stressDates,
      datasets: [
        { label: 'Stress Index', data: values, borderColor: '#C0392B', backgroundColor: 'rgba(192,57,43,0.08)', borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: 'origin', spanGaps: true },
        { label: '2.5', data: stressDates.map(() => 2.5), borderColor: 'rgba(192,57,43,0.35)', borderWidth: 1, borderDash: [5,4], pointRadius: 0, fill: false },
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

  setChartWindow(stressChart_, stressDates, initDays);

  document.getElementById('stress-insight').innerHTML = latest !== undefined
    ? `Current stress index: <strong>${latest.toFixed(2)}</strong> — ${
        latest > 2.5 ? '<strong style="color:var(--negative)">Elevated stress.</strong> Multiple series simultaneously outside historical norms.'
      : latest > 1.5 ? '<strong style="color:var(--warning)">Moderate stress.</strong> Some series elevated but no systemic shock signal.'
      : '<strong style="color:var(--positive)">Low stress.</strong> Markets within normal historical ranges.'}`
    : '';
}

window.setStressWindow = function(days, btn) {
  btn.parentElement.querySelectorAll('.window-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  setChartWindow(stressChart_, stressDates, days);
};

/* ── INIT ────────────────────────────────────────────────────── */
async function init() {
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';

  zData    = await fetchZscoreHistory(ALL_SERIES.map(s => s.id));
  allDates = Object.keys(zData['^GSPC'] || zData[ALL_SERIES[0].id] || {}).sort();

  buildToggles();
  timelineObj = await initAnomalyTimeline('anomalyTimelineChart', { window: 1260 });
  buildStressData();
  renderStress(1260);

  await Promise.all([loadAnomalyTable(), loadGauges()]);
}

init();
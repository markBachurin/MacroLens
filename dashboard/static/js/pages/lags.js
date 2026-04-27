/* ═══════════════════════════════════════════════════════════════
   pages/lags.js — Lead / Lag Analysis
   ═══════════════════════════════════════════════════════════════ */

import { fetchLagResults } from '../api.js';
import { TOOLTIP, CORRELATION_PAIRS, label, makeChart, sig } from '../chartUtils.js';

let lagChart_ = null;
let allData   = [];

/* ── PAIR SELECTOR ───────────────────────────────────────────── */
function buildPairSelect() {
  const sel = document.getElementById('pair-select');
  sel.innerHTML = CORRELATION_PAIRS.map(([a, b]) =>
    `<option value="${a}|${b}">${label(a)} → ${label(b)}</option>`
  ).join('');
}

window.onPairChange = function() {
  const [a, b] = document.getElementById('pair-select').value.split('|');
  renderLagChart(a, b);
};

/* ── LAG BAR CHART ───────────────────────────────────────────── */
function renderLagChart(a, b) {
  const pairData = allData
    .filter(d => d.series_a === a && d.series_b === b)
    .sort((x, y) => x.lag_days - y.lag_days);

  if (!pairData.length) {
    document.getElementById('lag-chart-title').textContent = `${label(a)} → ${label(b)}`;
    document.getElementById('lag-interpretation').innerHTML =
      '<span style="color:var(--text-muted)">No lag data available for this pair.</span>';
    return;
  }

  document.getElementById('lag-chart-title').textContent =
    `${label(a)} → ${label(b)}`;

  const lags   = pairData.map(d => `${d.lag_days}d`);
  const values = pairData.map(d => d.pearson_r);
  const colors = pairData.map(d => {
    const alpha = d.p_value < 0.05 ? 1 : 0.3;
    return d.pearson_r >= 0
      ? `rgba(29,131,72,${alpha})`
      : `rgba(192,57,43,${alpha})`;
  });

  lagChart_ = makeChart(lagChart_, 'lagChart', {
    type: 'bar',
    data: {
      labels: lags,
      datasets: [
        {
          label: 'Pearson r',
          data: values,
          backgroundColor: colors,
          borderRadius: 4,
          borderSkipped: false,
        },
        {
          // zero line
          type: 'line',
          label: '0',
          data: lags.map(() => 0),
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
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP,
          callbacks: {
            label: ctx => {
              if (ctx.dataset.label === '0') return null;
              const d = pairData[ctx.dataIndex];
              return [
                `r: ${d.pearson_r.toFixed(3)}`,
                `p: ${d.p_value.toFixed(4)} ${sig(d.p_value) || '(n.s.)'}`,
              ];
            },
          },
        },
      },
      scales: {
        x: { title: { display: true, text: 'Lag (trading days)' } },
        y: {
          title: { display: true, text: 'Pearson r' },
          grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,0.2)' : '#DDE3EA' },
        },
      },
      animation: { duration: 200 },
    },
  });

  renderInterpretation(a, b, pairData);
}

/* ── INTERPRETATION ──────────────────────────────────────────── */
function renderInterpretation(a, b, pairData) {
  const sigPairs = pairData.filter(d => d.p_value < 0.05);
  const best     = [...pairData].sort((x, y) => Math.abs(y.pearson_r) - Math.abs(x.pearson_r))[0];

  if (!best) {
    document.getElementById('lag-interpretation').innerHTML =
      '<span style="color:var(--text-muted)">No significant lead-lag relationship found.</span>';
    return;
  }

  const isSig      = best.p_value < 0.05;
  const direction  = best.pearson_r > 0 ? 'positive' : 'negative';
  const sigText    = isSig
    ? `<strong>statistically significant</strong> (p = ${best.p_value.toFixed(4)})`
    : `<span style="color:var(--text-muted)">not statistically significant</span> (p = ${best.p_value.toFixed(4)})`;

  document.getElementById('lag-interpretation').innerHTML = `
    <p style="margin-bottom:12px">
      Testing whether <strong>${label(a)}</strong> movements today 
      predict <strong>${label(b)}</strong> movements in the future.
    </p>
    <p style="margin-bottom:12px">
      Strongest relationship at <strong>lag ${best.lag_days} days</strong> — 
      r = <strong>${best.pearson_r.toFixed(3)}</strong>, ${sigText}.
    </p>
    <p style="margin-bottom:12px">
      ${best.lag_days > 0 && isSig
        ? `This suggests that movements in <strong>${label(a)}</strong> today tend to be 
           followed by <strong>${direction}</strong> correlated movements in 
           <strong>${label(b)}</strong> approximately 
           <strong>${best.lag_days} trading days</strong> (~${Math.round(best.lag_days * 7 / 5)} calendar days) later.`
        : best.lag_days === 0
          ? `Strongest correlation is at lag 0 — the relationship is contemporaneous, not predictive.`
          : `No statistically significant predictive relationship detected at standard thresholds.`
      }
    </p>
    <p style="font-size:11px; color:var(--text-muted)">
      ${sigPairs.length} of ${pairData.length} lag windows are statistically significant (p &lt; 0.05). 
      Faded bars indicate p &gt; 0.05 — interpret with caution.
    </p>`;
}

/* ── FULL TABLE ──────────────────────────────────────────────── */
function renderTable() {
  const sorted = [...allData].sort((a, b) => Math.abs(b.pearson_r) - Math.abs(a.pearson_r));
  document.getElementById('lag-tbody').innerHTML = sorted.map(d => `
    <tr>
      <td>${label(d.series_a)}</td>
      <td>${label(d.series_b)}</td>
      <td class="mono">${d.lag_days}d</td>
      <td class="mono" style="color:${d.pearson_r > 0 ? 'var(--positive)' : 'var(--negative)'}; font-weight:600">
        ${d.pearson_r?.toFixed(3) ?? '—'}
      </td>
      <td class="mono">${d.p_value?.toFixed(4) ?? '—'}</td>
      <td style="color:var(--blue-primary); font-weight:600">${sig(d.p_value) || '—'}</td>
    </tr>`).join('');
}

/* ── INIT ────────────────────────────────────────────────────── */
async function init() {
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toUTCString().slice(17, 22) + ' UTC';

  allData = await fetchLagResults();

  buildPairSelect();
  renderTable();

  // Default: first pair
  const [a, b] = CORRELATION_PAIRS[0];
  renderLagChart(a, b);
}

init();
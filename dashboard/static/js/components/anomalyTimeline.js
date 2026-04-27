/* ═══════════════════════════════════════════════════════════════
   components/anomalyTimeline.js — z-score timeline with pan/zoom
   ═══════════════════════════════════════════════════════════════ */

import { TOOLTIP, label, zoomPanConfig, setChartWindow } from '../chartUtils.js';
import { fetchZscoreHistory } from '../api.js';

const DEFAULT_SERIES = [
  { id: 'DCOILWTICO', color: '#0073BB' },
  { id: '^GSPC',      color: '#1D8348' },
  { id: '^VIX',       color: '#C0392B' },
  { id: 'GC=F',       color: '#D68910' },
  { id: 'DGS10',      color: '#8E44AD' },
  { id: 'FEDFUNDS',   color: '#5D6D7E' },
];

export async function initAnomalyTimeline(canvasId, opts = {}) {
  const series   = opts.series || DEFAULT_SERIES;
  const initDays = opts.window || 1260;

  const zData    = await fetchZscoreHistory(series.map(s => s.id));
  const refId    = series.find(s => s.id === '^GSPC')?.id || series[0].id;
  const allDates = Object.keys(zData[refId] || {}).sort();

  const datasets = series.map(s => ({
    label:           label(s.id),
    data:            allDates.map(d => zData[s.id]?.[d] ?? null),
    borderColor:     s.color,
    backgroundColor: 'transparent',
    borderWidth:     1.5,
    pointRadius:     0,
    tension:         0.2,
    spanGaps:        true,
  }));

  datasets.push({
    label: '+2.5σ', data: allDates.map(() => 2.5),
    borderColor: 'rgba(192,57,43,0.35)', borderWidth: 1,
    borderDash: [5, 4], pointRadius: 0, fill: false,
  });
  datasets.push({
    label: '−2.5σ', data: allDates.map(() => -2.5),
    borderColor: 'rgba(192,57,43,0.35)', borderWidth: 1,
    borderDash: [5, 4], pointRadius: 0, fill: false,
  });

  const chart = new Chart(document.getElementById(canvasId), {
    type: 'line',
    data: { labels: allDates, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10, padding: 12, usePointStyle: true } },
        tooltip: {
          ...TOOLTIP,
          callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2) ?? 'n/a'}σ` },
        },
        zoom: zoomPanConfig(),
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: {
          min: -6, max: 6,
          title: { display: true, text: 'Z-score (252d)' },
          grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,0.2)' : '#DDE3EA' },
        },
      },
      animation: { duration: 200 },
    },
  });

  setChartWindow(chart, allDates, initDays);

  return {
    setWindow(days) { setChartWindow(chart, allDates, days); },
    chart,
    allDates,
  };
}
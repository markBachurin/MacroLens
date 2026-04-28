/* ═══════════════════════════════════════════════════════════════
   api.js — MacroLens centralized API client
   All fetch calls go through here. One place to change the base URL.
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api`;

/**
 * Core fetch wrapper. Throws on non-ok responses.
 * @param {string} path - e.g. '/snapshot/latest/'
 * @returns {Promise<any>}
 */
async function apiFetch(path) {
  const response = await fetch(API_BASE + path);
  if (!response.ok) {
    throw new Error(`API error ${response.status} on ${path}`);
  }
  return response.json();
}

/* ── ENDPOINTS ───────────────────────────────────────────────── */

/** GET /snapshot/latest/ — latest value + zscore + anomaly_flag per series */
export async function fetchSnapshot() {
  return apiFetch('/snapshot/latest/');
}

/** GET /series/ — full series metadata list */
export async function fetchSeriesList() {
  return apiFetch('/series/');
}

/**
 * GET /series/<id>/ — normalized history for one series
 * @param {string} seriesId
 * @param {number} limit  - number of rows (default 9999 = all)
 * @param {number} offset
 */
export async function fetchSeriesDetail(seriesId, limit = 9999, offset = 0) {
  const id = encodeURIComponent(seriesId);
  return apiFetch(`/series/${id}/?limit=${limit}&offset=${offset}`);
}

/**
 * GET /correlations/ — latest full correlation matrix for a window
 * @param {number} window - 30 | 90 | 252
 */
export async function fetchCorrelations(window = 90) {
  return apiFetch(`/correlations/?window=${window}`);
}

/**
 * GET /correlations/<a>/<b>/ — rolling correlation time series for a pair
 * @param {string} seriesA
 * @param {string} seriesB
 * @param {number} window - 30 | 90 | 252
 */
export async function fetchCorrelationPair(seriesA, seriesB, window = 90) {
  const a = encodeURIComponent(seriesA);
  const b = encodeURIComponent(seriesB);
  return apiFetch(`/correlations/${a}/${b}/?window=${window}`);
}

/** GET /regression/latest/ — latest OLS betas, p-values, VIFs */
export async function fetchRegressionLatest() {
  return apiFetch('/regression/latest/');
}

/** GET /regression/history/ — full beta + r² history over time */
export async function fetchRegressionHistory() {
  return apiFetch('/regression/history/');
}

/** GET /anomalies/ — series currently flagged anomalous (latest per series) */
export async function fetchAnomalies() {
  return apiFetch('/anomalies/');
}

/** GET /lag/ — all lag results: all pairs, all lag days */
export async function fetchLagResults() {
  return apiFetch('/lag/');
}

/**
 * Fetch zscore history for multiple series IDs in parallel.
 * Returns a map: { seriesId: { date: zscore, ... }, ... }
 * @param {string[]} seriesIds
 */
export async function fetchZscoreHistory(seriesIds) {
  const results = await Promise.all(
    seriesIds.map(id => fetchSeriesDetail(id))
  );
  const map = {};
  seriesIds.forEach((id, i) => {
    map[id] = {};
    results[i].forEach(row => {
      map[id][row.date] = row.zscore_252d;
    });
  });
  return map;
}
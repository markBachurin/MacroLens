# MacroLens — API & Dashboard

## Overview

The presentation layer exposes the MacroLens warehouse via a Django REST Framework API and a multi-page Chart.js dashboard. It is the final layer in the pipeline — consuming data written by the analytics layer and making it accessible to users.

---

## Directory Structure

```
api/
└── api/
    ├── manage.py
    ├── api/               ← Django project package
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    └── core/              ← App package
        ├── models.py      ← Django ORM models mirroring warehouse tables
        ├── views.py       ← All views, function-based @api_view
        ├── urls.py        ← Endpoint routing
        └── apps.py

dashboard/
├── static/
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       ├── api.js                  ← Centralized API client (all fetch calls)
│       ├── chartUtils.js           ← Shared Chart.js config, formatters, color utils
│       ├── components/
│       │   └── anomalyTimeline.js  ← Reusable z-score multi-series timeline
│       └── pages/
│           ├── home.js             ← Current Regime page
│           ├── anomalies.js        ← Anomaly Monitor + Fear & Greed
│           ├── correlations.js     ← Correlation Heatmap + rolling TS
│           ├── macro.js            ← Real vs Nominal Oil + Yield Curve
│           ├── regression.js       ← OLS Beta Evolution
│           ├── lags.js             ← Lead / Lag Analysis
│           └── stress.js           ← Fear & Greed Index standalone page
└── templates/dashboard/
    ├── base.html           ← Shared nav, CDN scripts, layout shell
    ├── home.html
    ├── anomalies.html
    ├── correlations.html
    ├── factors.html
    ├── regression.html
    ├── lags.html
    └── stress.html
```

**Notes:**
- No `serializers.py` — views construct response dicts manually and return via `Response(data)`
- Django version: **6.0.4**
- All models have `managed = False` — tables are created by `scripts/init_db.py`, not Django migrations

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/series/` | List all 15 series with metadata |
| `GET` | `/api/series/{id}/` | Normalized history for one series. Params: `?limit=` (default 252), `?offset=` (default 0) |
| `GET` | `/api/snapshot/latest/` | Latest value + zscore + anomaly_flag per series |
| `GET` | `/api/correlations/` | Latest correlation matrix. Param: `?window=30\|90\|252` (default 90) |
| `GET` | `/api/correlations/{a}/{b}/` | Rolling correlation history for one pair. Param: `?window=` (default 90) |
| `GET` | `/api/regression/latest/` | Latest OLS regression result (single object) |
| `GET` | `/api/regression/history/` | Full beta + R² history over time |
| `GET` | `/api/anomalies/` | Series flagged anomalous in last 14 days, one row per series |
| `GET` | `/api/lag/` | All lag results — all pairs, all lag values |

All endpoints return JSON. No authentication required — public read-only API. CORS is open.

---

## Django Models (`core/models.py`)

Models mirror the warehouse tables exactly. Using Django ORM because queries are simple (filter by date, filter by series_id) and N+1 risk is zero — each endpoint fetches one resource type with a single query.

```python
from django.db import models

class RawSeries(models.Model):
    source = models.CharField(max_length=50)
    series_id = models.CharField(max_length=100)
    series_key = models.CharField(max_length=100)
    date = models.DateField()
    value = models.FloatField()
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "raw_series"
        unique_together = [("source", "series_id", "date")]

class NormalizedSeries(models.Model):
    series_id = models.CharField(max_length=100)
    series_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50)
    date = models.DateField()
    value = models.FloatField()
    pct_change = models.FloatField(null=True)
    zscore_252d = models.FloatField(null=True)
    is_forward_filled = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "normalized_series"
        unique_together = [("series_id", "date")]

class DailySnapshot(models.Model):
    series_id = models.CharField(max_length=100)
    date = models.DateField()
    value = models.FloatField(null=True)
    pct_change = models.FloatField(null=True)
    zscore_252d = models.FloatField(null=True)
    anomaly_flag = models.BooleanField(null=True)

    class Meta:
        managed = False
        db_table = "daily_snapshot"
        unique_together = [("series_id", "date")]

class CorrelationResult(models.Model):
    series_a = models.CharField(max_length=100)
    series_b = models.CharField(max_length=100)
    window_days = models.IntegerField()
    date = models.DateField()
    pearson_r = models.FloatField(null=True)
    p_value = models.FloatField(null=True)
    n_observations = models.IntegerField(null=True)

    class Meta:
        managed = False
        db_table = "correlation_results"

class RegressionResult(models.Model):
    date = models.DateField()
    beta_wti = models.FloatField(null=True)
    beta_fed = models.FloatField(null=True)
    beta_t10y = models.FloatField(null=True)
    r_squared = models.FloatField(null=True)
    p_value_wti = models.FloatField(null=True)
    p_value_fed = models.FloatField(null=True)
    p_value_t10y = models.FloatField(null=True)
    vif_wti = models.FloatField(null=True)
    vif_fed = models.FloatField(null=True)
    vif_t10y = models.FloatField(null=True)

    class Meta:
        managed = False
        db_table = "regression_results"

class LagResult(models.Model):
    series_a = models.CharField(max_length=100)
    series_b = models.CharField(max_length=100)
    lag_days = models.IntegerField()
    date = models.DateField()
    pearson_r = models.FloatField(null=True)
    p_value = models.FloatField(null=True)

    class Meta:
        managed = False
        db_table = "lag_results"

class AnomalyFlag(models.Model):
    series_id = models.CharField(max_length=100)
    date = models.DateField()
    zscore = models.FloatField(null=True)
    direction = models.CharField(max_length=10, null=True)
    threshold = models.FloatField(null=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "anomaly_flags"
        unique_together = [("series_id", "date")]
```

---

## Views (`core/views.py`)

All views are function-based with `@api_view(["GET"])`. No class-based generic views.

### `/api/series/`
Returns all series from `SERIES_CONFIG` as a list with fields: `series_key`, `series_id`, `name`, `source`, `unit`, `category`, `frequency`. No DB query.

### `/api/series/{id}/`
Filters `NormalizedSeries` by `series_id`, ordered newest-first. Supports `?limit=` (default 252) and `?offset=` (default 0).

### `/api/snapshot/latest/`
Returns the most recent snapshot row per series using `distinct("series_id")` ordered by `-date`. Used by stat cards and z-score gauges.

### `/api/correlations/`
Accepts `?window=30|90|252` (default 90). Returns latest result per pair using `Max("date")` annotation per `(series_a, series_b)` group, then filters to those dates.

### `/api/correlations/{a}/{b}/`
Returns full rolling history for one pair ordered by `date`. Accepts `?window=` (default 90).

### `/api/regression/latest/`
Returns a single dict — the most recent row from `regression_results` ordered by `-date`.

### `/api/regression/history/`
Returns all rows from `regression_results` ordered by `date` ascending. Fields: `date`, `beta_wti`, `beta_fed`, `beta_t10y`, `r_squared`.

### `/api/anomalies/`
Reads from `DailySnapshot` (not `anomaly_flags` table). Filters `anomaly_flag=True` and `date >= today - 14 days`. Returns latest per series via `distinct("series_id")`.

### `/api/lag/`
Returns all rows from `lag_results` ordered by `series_a`, `series_b`, `lag_days`.

---

## URL Configuration

```python
# api/api/api/urls.py
urlpatterns = [
    path("api/", include("core.urls")),
    path("dashboard/", include("core.dashboard_urls")),
]

# api/api/core/urls.py
urlpatterns = [
    path("series/",                          views.series_list),
    path("series/<str:series_id>/",          views.series_detail),
    path("snapshot/latest/",                 views.snapshot_latest),
    path("correlations/",                    views.correlations_list),
    path("correlations/<str:series_a>/<str:series_b>/", views.correlations_pair),
    path("regression/latest/",               views.regression_latest),
    path("regression/history/",              views.regression_history),
    path("anomalies/",                       views.anomalies_list),
    path("lag/",                             views.lag_list),
]
```

---

## Dashboard

Multi-page application. No build step. Chart.js 4.4.1 + chartjs-plugin-zoom 2.0.1 + hammer.js 2.0.8 loaded from CDN. All JS uses ES6 modules (`type="module"`).

### Pages

| Page | URL | JS Module | Description |
|---|---|---|---|
| Current Regime | `/dashboard/` | `pages/home.js` | Stat cards, anomaly timeline, mini heatmap, yield curve, regression betas, z-score gauges |
| Anomaly Monitor | `/dashboard/anomalies/` | `pages/anomalies.js` | Anomaly table, z-score gauges, anomaly timeline, stress index |
| Correlations | `/dashboard/correlations/` | `pages/correlations.js` | Full heatmap (all 3 windows), rolling correlation time series, pair detail panel |
| Macro Factors | `/dashboard/factors/` | `pages/macro.js` | Nominal vs real WTI chart, yield curve spread vs S&P 500 dual-axis chart |
| Regression | `/dashboard/regression/` | `pages/regression.js` | Latest beta table, beta evolution chart, R² over time chart |
| Lag Analysis | `/dashboard/lags/` | `pages/lags.js` | Bar chart of r by lag, interpretation text, full results table |
| Fear & Greed | `/dashboard/stress/` | `pages/stress.js` | Stress index time series, per-series z-score breakdown, current stress banner |

### Shared Modules

**`api.js`** — Centralized fetch client. All API calls go through here. Exports: `fetchSnapshot`, `fetchSeriesList`, `fetchSeriesDetail`, `fetchCorrelations`, `fetchCorrelationPair`, `fetchRegressionLatest`, `fetchRegressionHistory`, `fetchAnomalies`, `fetchLagResults`, `fetchZscoreHistory`.

**`chartUtils.js`** — Shared Chart.js configuration and utilities. Exports: `TOOLTIP` (tooltip style preset), `COLORS` (palette), `rColor(r)` (Pearson r → RGB for heatmap), `textOnBg(r)`, `fmtVal(v, seriesId)` (value formatter), `sig(p)` (significance stars), `SERIES_LABELS` (series_id → human label), `label(seriesId)`, `CORRELATION_PAIRS`, `startClock(elementId)`, `activateWindowBtn`, `makeChart`, `sliceDates`, `zoomPanConfig()`, `setChartWindow(chart, allDates, days)`.

**`components/anomalyTimeline.js`** — Reusable multi-series z-score chart with zoom/pan. Used on Home and Anomalies pages. Export: `initAnomalyTimeline(canvasId, opts)` → returns `{ chart, allDates, setWindow(days) }`.

### Design Decision: No React

React adds a build toolchain (Node.js, npm, bundler), a development server, and deployment complexity. Chart.js in plain HTML with ES6 modules achieves the required interactivity in a fraction of the time. For a data engineering project, the dashboard is a demonstration vehicle — not the primary engineering artifact.

---

## Django Settings (`api/api/api/settings.py`)

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("PG_DB", "db"),
        "USER": os.getenv("PG_USER", "user"),
        "PASSWORD": os.getenv("PG_PASSWORD", "password"),
        "HOST": os.getenv("PG_HOST", "localhost"),
        "PORT": os.getenv("PG_PORT", "5432"),
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "core",
]

STATICFILES_DIRS = [BASE_DIR / 'dashboard' / 'static']
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'dashboard' / 'templates']

CORS_ALLOW_ALL_ORIGINS = True
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
```

---

## Key Interview Questions

**Q: Why Django ORM instead of raw SQL for the API?**

The API queries are simple: filter by `series_id`, filter by `date`, order by `date`, take a limit. Django ORM handles these cleanly. Raw SQL would be justified if queries required complex joins or window functions — neither is needed here.

**Q: How do you prevent N+1 queries?**

Each endpoint fetches exactly one resource type. The snapshot endpoint fetches all series for one date in a single query — not one query per series. Django ORM's `filter()` generates a single SQL `WHERE` clause.

**Q: Why no pagination on the correlation endpoint?**

The correlation matrix is at most 9 pairs × 3 windows = 27 rows for the latest date. Pagination adds API surface area and client complexity for no benefit at this scale. The series history endpoint does paginate (default 252 rows) because historical data can span 20 years = ~5,000 rows.

**Q: How would you add authentication if needed?**

DRF has built-in `TokenAuthentication` and `SessionAuthentication`. Adding `permission_classes = [IsAuthenticated]` to each view would be a one-afternoon change. The current design deliberately omits auth because the API is read-only public data.

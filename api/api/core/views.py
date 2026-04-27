import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import DailySnapshot, NormalizedSeries, CorrelationResult, RegressionResult, LagResult
from ingestion.config.series_config import SERIES_CONFIG
from datetime import date, timedelta



@api_view(["GET"])
def snapshot_latest(request):
    snapshots = (DailySnapshot.objects.order_by("series_id", "-date").distinct("series_id"))

    data = [
        {
            "series_id": s.series_id,
            "date": s.date,
            "value": s.value,
            "pct_change": s.pct_change,
            "zscore_252d": s.zscore_252d,
            "anomaly_flag": s.anomaly_flag,
        }
        for s in snapshots
    ]

    return Response(data)

@api_view(["GET"])
def series_list(request):
    from ingestion.config.series_config import SERIES_CONFIG
    data = [
        {
            "series_key": key,
            "series_id": val["series_id"],
            "name": val["name"],
            "source": val["source"],
            "unit": val["unit"],
            "category": val["category"],
            "frequency": val["frequency"],
        }
        for key, val in SERIES_CONFIG.items()
    ]
    return Response(data)


@api_view(["GET"])
def series_detail(request, series_id):
    limit = int(request.GET.get("limit", 252))
    offset = int(request.GET.get("offset", 0))

    qs = (
        NormalizedSeries.objects
        .filter(series_id=series_id)
        .order_by("-date")[offset:offset + limit]
    )

    data = [
        {
            "date": s.date,
            "value": s.value,
            "pct_change": s.pct_change,
            "zscore_252d": s.zscore_252d,
            "is_forward_filled": s.is_forward_filled,
        }
        for s in qs
    ]
    return Response(data)


@api_view(["GET"])
def correlations_list(request):
    window = int(request.GET.get("window", 90))

    from django.db.models import Max

    latest_per_pair = (
        CorrelationResult.objects
        .filter(window_days=window)
        .values("series_a", "series_b")
        .annotate(latest=Max("date"))
    )

    from django.db.models import Q
    query = Q()
    for row in latest_per_pair:
        query |= Q(
            series_a=row["series_a"],
            series_b=row["series_b"],
            window_days=window,
            date=row["latest"]
        )

    qs = CorrelationResult.objects.filter(query)

    data = [
        {
            "series_a": c.series_a,
            "series_b": c.series_b,
            "window_days": c.window_days,
            "date": c.date,
            "pearson_r": c.pearson_r,
            "p_value": c.p_value,
            "n_observations": c.n_observations,
        }
        for c in qs
    ]
    return Response(data)


@api_view(["GET"])
def correlations_pair(request, series_a, series_b):
    window = int(request.GET.get("window", 90))

    qs = CorrelationResult.objects.filter(
        series_a=series_a,
        series_b=series_b,
        window_days=window
    ).order_by("date")

    data = [
        {
            "date": c.date,
            "pearson_r": c.pearson_r,
            "p_value": c.p_value,
            "n_observations": c.n_observations,
        }
        for c in qs
    ]
    return Response(data)


@api_view(["GET"])
def regression_latest(request):
    latest = RegressionResult.objects.order_by("-date").first()

    if not latest:
        return Response({"error": "No regression results found"}, status=404)

    data = {
        "date": latest.date,
        "beta_wti": latest.beta_wti,
        "beta_fed": latest.beta_fed,
        "beta_t10y": latest.beta_t10y,
        "r_squared": latest.r_squared,
        "p_value_wti": latest.p_value_wti,
        "p_value_fed": latest.p_value_fed,
        "p_value_t10y": latest.p_value_t10y,
        "vif_wti": latest.vif_wti,
        "vif_fed": latest.vif_fed,
        "vif_t10y": latest.vif_t10y,
    }
    return Response(data)



@api_view(["GET"])
def anomalies_list(request):
    cutoff = date.today() - timedelta(days=14)
    snapshots = DailySnapshot.objects.filter(
        anomaly_flag=True,
        date__gte=cutoff
    ).order_by("series_id", "-date").distinct("series_id")

    data = [
        {
            "series_id": s.series_id,
            "date": s.date,
            "value": s.value,
            "zscore_252d": s.zscore_252d,
            "anomaly_flag": s.anomaly_flag,
        }
        for s in snapshots
    ]
    return Response(data)

@api_view(["GET"])
def regression_history(request):
    qs = RegressionResult.objects.order_by("date")
    return Response([{
        "date": r.date,
        "beta_wti": r.beta_wti,
        "beta_fed": r.beta_fed,
        "beta_t10y": r.beta_t10y,
        "r_squared": r.r_squared,
    } for r in qs])

@api_view(["GET"])
def lag_list(request):
    qs = LagResult.objects.all().order_by("series_a", "series_b", "lag_days")
    return Response([{
        "series_a": r.series_a,
        "series_b": r.series_b,
        "lag_days": r.lag_days,
        "date": r.date,
        "pearson_r": r.pearson_r,
        "p_value": r.p_value,
    } for r in qs])



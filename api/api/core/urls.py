from django.urls import path
from . import views

urlpatterns = [
    path("series/", views.series_list),
    path("series/<str:series_id>/", views.series_detail),
    path("snapshot/latest/", views.snapshot_latest),
    path("correlations/", views.correlations_list),
    path("correlations/<str:series_a>/<str:series_b>/", views.correlations_pair),
    path("regression/latest/", views.regression_latest),
    path("anomalies/", views.anomalies_list),
    path("regression/history/", views.regression_history),
    path("lag/", views.lag_list),
]
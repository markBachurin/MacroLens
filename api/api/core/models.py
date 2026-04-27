from django.db import models

# Create your models here.


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

class DailySnapshot(models.Model):
    series_id = models.CharField(max_length=100)
    date = models.DateField()
    value = models.FloatField(null=True)
    pct_change = models.FloatField(null=True)
    zscore_252d = models.FloatField(null=True)
    anomaly_flag = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "daily_snapshot"


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
    direction = models.CharField(max_length=10)
    threshold = models.FloatField(default=2.5)
    resolved = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "anomaly_flags"
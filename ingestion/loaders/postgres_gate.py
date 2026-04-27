from ingestion.config.series_config import get_field

from ingestion.loaders.base import StorageGate
from ingestion.loaders.db_connection import get_connection
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()

class Postgres_StorageGate(StorageGate):
    def __init__(self):
        self.connection = get_connection()

    def platform(self) -> str:
        return "postgres"

    def upload_series(self, records: list[dict], source: str, series_key: str, state: str = "raw") -> None:
        cursor = self.connection.cursor()

        for record in records:
            cursor.execute(f"""
                INSERT INTO {state}_series (source, series_id, series_key, date, value)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source, series_id, date)
                DO UPDATE SET value = EXCLUDED.value, ingested_at = NOW();
            """, (
                source,
                get_field(series_key, "series_id"),
                series_key,
                record["date"],
                record["value"],
            ))

        self.connection.commit()
        cursor.close()

    def upload_normalized_series(
            self,
            records: list[dict],
            series_key: str,
    ):
        cursor = self.connection.cursor()

        for record in records:
            cursor.execute("""
                INSERT INTO normalized_series(
                    series_id, series_name, category, date, value, 
                    pct_change, zscore_252d, is_forward_filled
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_id, date)
                DO UPDATE SET
                    value = EXCLUDED.value, 
                    pct_change = EXCLUDED.pct_change, 
                    zscore_252d = EXCLUDED.zscore_252d,
                    is_forward_filled = EXCLUDED.is_forward_filled;
            """,(
                get_field(series_key, "series_id"),
                get_field(series_key, "name"),
                get_field(series_key, "category"),
                record["date"],
                record["value"],
                record.get("pct_change", None),
                record.get("zscore_252d", None),
                record.get("is_forward_filled"),
            ))

        self.connection.commit()
        cursor.close()

    def query_raw_by_series_key(self, series_key: str) -> list[Tuple]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT date, value FROM raw_series WHERE series_key = %s ORDER BY date ASC
        """, (series_key,))
        return cursor.fetchall()

    def query_snapshot_entries(self) -> list[tuple]:
        cursor = self.connection.cursor()
        cursor.execute("""
                    SELECT series_id, date, value, pct_change, zscore_252d
                    FROM normalized_series
                    WHERE zscore_252d IS NOT NULL
                    ORDER BY series_id, date ASC
                """)
        return cursor.fetchall()

    def upload_snapshot(self, records: list[dict]) -> None:
        cursor = self.connection.cursor()

        for record in records:
            cursor.execute(f"""
                INSERT INTO daily_snapshot (series_id, date, value, pct_change, zscore_252d, anomaly_flag)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_id, date)
                DO UPDATE SET 
                    value = EXCLUDED.value, 
                    pct_change = EXCLUDED.pct_change,
                    zscore_252d = EXCLUDED.zscore_252d,
                    anomaly_flag = EXCLUDED.anomaly_flag;
            """,(
                record["series_id"],
                record["date"],
                record["value"],
                record["pct_change"],
                record["zscore_252d"],
                record["anomaly_flag"],
            ))
        self.connection.commit()
        cursor.close()

    def upload_correlations(self, records: list[dict]) -> None:
        cursor = self.connection.cursor()

        for record in records:
            cursor.execute("""
                INSERT INTO correlation_results 
                    (series_a, series_b, window_days, date, pearson_r, p_value, n_observations)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_a, series_b, window_days, date)
                DO UPDATE SET
                    pearson_r = EXCLUDED.pearson_r,
                    p_value = EXCLUDED.p_value,
                    n_observations = EXCLUDED.n_observations;
            """, (
                record["series_a"],
                record["series_b"],
                record["window_days"],
                record["date"],
                record["pearson_r"],
                record["p_value"],
                record["n_observations"],
            ))

        self.connection.commit()
        cursor.close()

    def query_normalized_by_series_id(self, series_id: str) -> list[Tuple]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT date, value, pct_change, zscore_252d
            FROM normalized_series WHERE series_id = %s ORDER BY date ASC
        """, (series_id,))
        return cursor.fetchall()

    def upload_lag_results(self, records: list[dict]) -> None:
        cursor = self.connection.cursor()

        for record in records:
            cursor.execute("""
                INSERT INTO lag_results
                (series_a, series_b, lag_days, date, pearson_r, p_value)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_a, series_b, lag_days, date)
                DO UPDATE SET
                    pearson_r = EXCLUDED.pearson_r,
                    p_value = EXCLUDED.p_value;
            """, (
                record["series_a"],
                record["series_b"],
                record["lag_days"],
                record["date"],
                record["pearson_r"],
                record["p_value"],
            ))
        self.connection.commit()
        cursor.close()

    def upload_regression_results(self, records: list[dict]) -> None:
        cursor = self.connection.cursor()

        for record in records:
            cursor.execute("""
                INSERT INTO regression_results
                    (date, beta_wti, beta_fed, beta_t10y, r_squared,
                     p_value_wti, p_value_fed, p_value_t10y,
                     vif_wti, vif_fed, vif_t10y)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date)
                DO UPDATE SET
                    beta_wti = EXCLUDED.beta_wti,
                    beta_fed = EXCLUDED.beta_fed,
                    beta_t10y = EXCLUDED.beta_t10y,
                    r_squared = EXCLUDED.r_squared,
                    p_value_wti = EXCLUDED.p_value_wti,
                    p_value_fed = EXCLUDED.p_value_fed,
                    p_value_t10y = EXCLUDED.p_value_t10y,
                    vif_wti = EXCLUDED.vif_wti,
                    vif_fed = EXCLUDED.vif_fed,
                    vif_t10y = EXCLUDED.vif_t10y;
            """, (
                record["date"],
                record["beta_wti"],
                record["beta_fed"],
                record["beta_t10y"],
                record["r_squared"],
                record["p_value_wti"],
                record["p_value_fed"],
                record["p_value_t10y"],
                record["vif_wti"],
                record["vif_fed"],
                record["vif_t10y"],
            ))

        self.connection.commit()
        cursor.close()

    def close(self):
        if self.connection and not self.connection.closed:
            self.connection.close()


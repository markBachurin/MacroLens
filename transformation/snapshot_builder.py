from ingestion.loaders.postgres_gate import Postgres_Client
from ingestion.config.series_config import SERIES_CONFIG

def build_snapshots() -> None:
    gate = Postgres_Client()

    for series_key, data in SERIES_CONFIG.items():
        rows = gate.query_normalized_by_series_id(SERIES_CONFIG[series_key]["series_id"])

        if not rows:
            continue

        records = []
        for row in rows:
            date, value, pct_change, zscore_252d = row

            anomaly_flags = abs(zscore_252d) > 2.5 if zscore_252d is not None else False

            records.append({
                "series_id": data["series_id"],
                "date": date,
                "value": value,
                "pct_change": pct_change,
                "zscore_252d": zscore_252d,
                "anomaly_flag": anomaly_flags,
            })

        gate.upload_snapshot(records)

    gate.close()

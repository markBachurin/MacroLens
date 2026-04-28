from ingestion.loaders.db_connection import get_connection
from config.settings import settings


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_series (
            id SERIAL PRIMARY KEY,
            source VARCHAR(50) NOT NULL,
            series_id VARCHAR(100) NOT NULL,
            series_key VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            value FLOAT NOT NULL,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_raw_source_series_date 
                UNIQUE(source, series_id, date)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS normalized_series (
            id SERIAL PRIMARY KEY,
            series_id VARCHAR(100) NOT NULL,
            series_name VARCHAR(255) NOT NULL,
            category VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            value FLOAT NOT NULL,
            pct_change FLOAT,
            zscore_252d FLOAT,
            is_forward_filled BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT unique_normalized_series_date 
                UNIQUE(series_id, date)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            id SERIAL PRIMARY KEY,
            series_id VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            value FLOAT,
            pct_change FLOAT,
            zscore_252d FLOAT,
            anomaly_flag BOOLEAN,
            CONSTRAINT unique_snapshot_series_date 
                UNIQUE(series_id, date)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS correlation_results (
            id SERIAL PRIMARY KEY,
            series_a VARCHAR(100) NOT NULL,
            series_b VARCHAR(100) NOT NULL,
            window_days INT NOT NULL,
            date DATE NOT NULL,
            pearson_r FLOAT,
            p_value FLOAT,
            n_observations INT,
            CONSTRAINT unique_correlation 
                UNIQUE(series_a, series_b, window_days, date)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regression_results (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL UNIQUE,
            beta_wti FLOAT,
            beta_fed FLOAT,
            beta_t10y FLOAT,
            r_squared FLOAT,
            p_value_wti FLOAT,
            p_value_fed FLOAT,
            p_value_t10y FLOAT,
            vif_wti FLOAT,
            vif_fed FLOAT,
            vif_t10y FLOAT
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomaly_flags (
            id SERIAL PRIMARY KEY,
            series_id VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            zscore FLOAT,
            direction VARCHAR(10),
            threshold FLOAT,
            resolved BOOLEAN DEFAULT FALSE,
            CONSTRAINT unique_anomaly 
                UNIQUE(series_id, date)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lag_results (
            id SERIAL PRIMARY KEY,
            series_a VARCHAR(100) NOT NULL,
            series_b VARCHAR(100) NOT NULL,
            lag_days INT NOT NULL,
            date DATE NOT NULL,
            pearson_r FLOAT,
            p_value FLOAT,
            UNIQUE(series_a, series_b, lag_days, date)
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("All tables created successfully.")

if __name__ == "__main__":
    init_db()
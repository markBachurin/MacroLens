import pytest
from unittest.mock import patch, MagicMock


# ── DagBag (import errors + existence) ───────────────────────────────────────

@pytest.fixture(scope="session")
def dagbag():
    from airflow.models import DagBag
    return DagBag(dag_folder="dags/", include_examples=False)


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}, \
        f"DAG import errors: {dagbag.import_errors}"


def test_all_dags_loaded(dagbag):
    expected = {
        "ingest_fred",
        "ingest_yfinance",
        "ingest_treasury",
        "ingest_alphavantage",
        "transform",
        "analytics",
    }
    assert expected.issubset(set(dagbag.dags.keys())), \
        f"Missing DAGs: {expected - set(dagbag.dags.keys())}"


# ── Ingest DAG structure (shared pattern) ────────────────────────────────────

@pytest.mark.parametrize("dag_id, source", [
    ("ingest_fred", "fred"),
    ("ingest_yfinance", "yfinance"),
    ("ingest_treasury", "treasury"),
    ("ingest_alphavantage", "alphavantage"),
])
def test_ingest_dag_tasks_exist(dagbag, dag_id, source):
    dag = dagbag.dags[dag_id]
    task_ids = {t.task_id for t in dag.tasks}
    expected = {
        f"extract_{source}",
        f"archive_raw_{source}",
        f"validate_{source}",
        f"load_{source}",
    }
    assert expected == task_ids, \
        f"{dag_id}: expected tasks {expected}, got {task_ids}"


@pytest.mark.parametrize("dag_id, source", [
    ("ingest_fred", "fred"),
    ("ingest_yfinance", "yfinance"),
    ("ingest_treasury", "treasury"),
    ("ingest_alphavantage", "alphavantage"),
])
def test_ingest_dag_task_order(dagbag, dag_id, source):
    dag = dagbag.dags[dag_id]

    archive = dag.get_task(f"archive_raw_{source}")
    validate = dag.get_task(f"validate_{source}")
    load = dag.get_task(f"load_{source}")

    assert f"extract_{source}" in archive.upstream_task_ids
    assert f"archive_raw_{source}" in validate.upstream_task_ids
    assert f"validate_{source}" in load.upstream_task_ids


@pytest.mark.parametrize("dag_id", [
    "ingest_fred",
    "ingest_yfinance",
    "ingest_treasury",
    "ingest_alphavantage",
])
def test_ingest_dag_schedule(dagbag, dag_id):
    dag = dagbag.dags[dag_id]
    assert str(dag.schedule_interval) == "0 4 * * *"
    assert dag.catchup is False


# ── Transform DAG ─────────────────────────────────────────────────────────────

def test_transform_dag_tasks_exist(dagbag):
    dag = dagbag.dags["transform"]
    task_ids = {t.task_id for t in dag.tasks}
    assert task_ids == {"normalize", "compute_derived", "build_snapshots"}


def test_transform_dag_task_order(dagbag):
    dag = dagbag.dags["transform"]

    derived = dag.get_task("compute_derived")
    snapshots = dag.get_task("build_snapshots")

    assert "normalize" in derived.upstream_task_ids
    assert "compute_derived" in snapshots.upstream_task_ids


def test_transform_dag_schedule(dagbag):
    dag = dagbag.dags["transform"]
    assert str(dag.schedule_interval) == "0 5 * * *"
    assert dag.catchup is False


# ── Analytics DAG ─────────────────────────────────────────────────────────────

def test_analytics_dag_tasks_exist(dagbag):
    dag = dagbag.dags["analytics"]
    task_ids = {t.task_id for t in dag.tasks}
    assert task_ids == {"compute_correlations", "compute_regressions", "compute_lag_analysis"}


def test_analytics_dag_task_order(dagbag):
    dag = dagbag.dags["analytics"]

    regression = dag.get_task("compute_regressions")
    lag = dag.get_task("compute_lag_analysis")

    assert "compute_correlations" in regression.upstream_task_ids
    assert "compute_regressions" in lag.upstream_task_ids


def test_analytics_dag_schedule(dagbag):
    dag = dagbag.dags["analytics"]
    assert str(dag.schedule_interval) == "0 6 * * *"
    assert dag.catchup is False


# ── DAG factory unit tests (no Airflow needed) ────────────────────────────────

class TestDagFactory:
    @patch("ingestion.loaders.postgres_gate.get_connection")
    @patch("ingestion.config.series_config.get_source_series")
    def test_load_task_closes_connection_on_error(self, mock_series, mock_conn):
        """Postgres connection must be closed even if upload raises."""
        from dags.dag_factory import create_load_task

        mock_conn_instance = MagicMock()
        mock_conn_instance.closed = False
        mock_conn.return_value = mock_conn_instance

        mock_series.return_value = {"WTI": {"series_id": "DCOILWTICO"}}

        mock_cursor = MagicMock()
        mock_conn_instance.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn_instance.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = Exception("DB error")

        load_fn = create_load_task("fred")
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = {"WTI": [{"date": "2024-01-01", "value": 75.0}]}

        with pytest.raises(Exception, match="DB error"):
            load_fn(ti=mock_ti)

        mock_conn_instance.close.assert_called_once()

    def test_validate_task_filters_invalid_records(self):
        """Validate task should drop invalid records and not crash."""
        from dags.dag_factory import create_validate_task

        validate_fn = create_validate_task("fred")
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = {
            "WTI": [
                {"date": "2024-01-01", "value": 75.0},
                {"date": "2024-01-01", "value": 76.0},  # duplicate
            ]
        }

        validate_fn(ti=mock_ti)

        pushed = mock_ti.xcom_push.call_args
        validated = pushed[1]["value"] if pushed[1] else pushed[0][1]
        assert len(validated["WTI"]) == 1
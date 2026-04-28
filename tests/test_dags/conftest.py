import os

def pytest_configure(config):
    os.environ.setdefault("AIRFLOW_HOME", "/tmp/airflow_test")
    os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "false")
    os.environ.setdefault("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", "sqlite:////tmp/airflow_test/airflow.db")
    os.environ.setdefault("LANG", "en_US.UTF-8")  # add this line

    import airflow
    from airflow.utils import db
    db.initdb()
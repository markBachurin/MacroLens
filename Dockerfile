FROM apache/airflow:2.9.0

USER root
RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/opt/airflow:/opt/airflow/dags

USER airflow
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "."
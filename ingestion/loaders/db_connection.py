import psycopg2
from config.settings import settings

def get_connection():
    return psycopg2.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            database=settings.pg_db,
            user=settings.pg_user,
            password=settings.pg_password
        )
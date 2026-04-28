from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    database_url: str

    fred_api_key: str
    alpha_vantage_api_key: str

    pg_host: str
    pg_port: str
    pg_db: str
    pg_user: str
    pg_password: str

    debug: str
    django_secret_key: str
    secret_key:str

    s3_bucket: str
    aws_access_key: str
    aws_secret_access_key:str

    model_config =  SettingsConfigDict(
        env_file = Path(__file__).parent.parent / ".env",
        env_file_encoding = "utf-8"
    )

settings = Settings()
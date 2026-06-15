from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://solna:solna@localhost:5432/solna"

    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "solna-media"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    public_base_url: str = "http://localhost:8000"
    gallery_token_bytes: int = 16
    ingest_api_key: str = "dev-ingest-key"
    gallery_poll_interval_ms: int = 3000

    ftp_host: str = "localhost"
    ftp_port: int = 21
    ftp_root: str = "/data/ftp"


@lru_cache
def get_settings() -> Settings:
    return Settings()

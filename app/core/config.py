from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "PulseNotify"
    app_env: str = "development"
    secret_key: str
    access_token_expire_minutes: int = 30
    database_url: str
    rabbitmq_url: str
    celery_broker_url: str
    celery_result_backend: str
    redis_url: str
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_pass: str
    smtp_from: str
    smtp_user_email: str
    prometheus_port: int = 9090
    grafana_port: int = 3000
    flower_port: int = 5555
    prometheus_multiproc_dir: Optional[str] = "/tmp/prometheus_multiproc"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
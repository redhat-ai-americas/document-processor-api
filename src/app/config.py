from enum import Enum

from pydantic_settings import BaseSettings


class Device(str, Enum):
    cpu = "cpu"
    cuda = "cuda"
    mps = "mps"


class Settings(BaseSettings):
    app_name: str = "document-processor-api"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    max_file_size_mb: int = 50
    docling_artifacts_path: str = "/opt/app-root/src/.cache/docling/models"
    device: Device = Device.cpu

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://insurance_admin:changeme@localhost:5432/insurance_ai"
    storage_root: str = "./storage"
    max_upload_size_bytes: int = 25 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

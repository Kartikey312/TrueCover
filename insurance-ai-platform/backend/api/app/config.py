from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://insurance_admin:changeme@localhost:5432/insurance_ai"
    storage_root: str = "./storage"
    max_upload_size_bytes: int = 25 * 1024 * 1024
    qdrant_url: str = "http://localhost:6333"

    jwt_secret_key: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    staff_token_expire_minutes: int = 8 * 60
    member_token_expire_minutes: int = 24 * 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

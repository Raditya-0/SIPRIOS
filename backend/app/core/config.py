from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "sqlite:///./siprios.db"

    SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    STORAGE_PROVIDER: str = "local"
    STORAGE_BUCKET: str = "siprios-files"
    STORAGE_REGION: str = "ap-southeast-1"
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    STORAGE_PUBLIC_BASE_URL: str = "http://localhost:8000/static"

    MAX_FILE_SIZE_MB: int = 5
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp"
    ALLOWED_DOC_TYPES: str = "application/pdf"

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_NAMA: str = "Administrator SIPRIOS"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_image_types_list(self) -> list[str]:
        return [t.strip() for t in self.ALLOWED_IMAGE_TYPES.split(",")]

    @property
    def allowed_doc_types_list(self) -> list[str]:
        return [t.strip() for t in self.ALLOWED_DOC_TYPES.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

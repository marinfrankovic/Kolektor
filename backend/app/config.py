from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KOLEKTOR_", extra="ignore")

    database_url: str = "postgresql+psycopg://kolektor:kolektor@db:5432/kolektor"
    media_root: str = "/data/media"
    static_root: str = "/app/static"

    secret_key: str = ""
    session_ttl_hours: int = 720

    # Reverse proxy, TLS and a custom domain are all optional. The defaults below
    # let the app run as-is on a LAN at http://<host>:8100 with no proxy at all.
    behind_proxy: bool = False
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    public_base_url: str = ""
    cors_origins: str = ""

    initial_user_email: str = ""
    initial_user_password: str = ""
    default_language: str = "en"

    max_upload_mb: int = 40
    max_source_megapixels: int = 80
    preview_max_px: int = 1600
    thumb_max_px: int = 400
    jpeg_quality: int = 90

    autocrop: bool = True
    autoenhance: bool = False
    enable_rembg: bool = False
    enable_ocr: bool = True
    ocr_languages: str = "eng"

    worker_poll_seconds: float = 2.0
    worker_max_attempts: int = 3

    login_max_attempts: int = 8
    login_window_seconds: int = 300

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    BOT_TOKEN: str = ""
    ALLOWED_USER_IDS: Optional[str] = ""

    # Instagram Graph API
    IG_USER_ID: str = ""
    IG_ACCESS_TOKEN: str = ""
    IG_GRAPH_API_VERSION: str = "v21.0"

    # Google Gemini AI
    GEMINI_API_KEY: Optional[str] = ""

    # Storage Type: "r2", "s3", or "local"
    STORAGE_TYPE: str = "r2"

    # =========================================================================
    # Cloudflare R2 Dedicated Settings
    # =========================================================================
    R2_ACCOUNT_ID: Optional[str] = ""
    R2_ACCESS_KEY_ID: Optional[str] = ""
    R2_SECRET_ACCESS_KEY: Optional[str] = ""
    R2_BUCKET_NAME: Optional[str] = ""
    R2_PUBLIC_DOMAIN: Optional[str] = ""

    # =========================================================================
    # Generic S3 Settings (AWS S3, MinIO, or generic S3-compatible)
    # =========================================================================
    S3_ENDPOINT_URL: Optional[str] = ""
    S3_ACCESS_KEY_ID: Optional[str] = ""
    S3_SECRET_ACCESS_KEY: Optional[str] = ""
    S3_BUCKET_NAME: Optional[str] = ""
    S3_PUBLIC_DOMAIN: Optional[str] = ""

    # =========================================================================
    # Local Storage & Security Settings
    # =========================================================================
    LOCAL_STORAGE_DIR: str = "/app/data/media"
    LOCAL_PUBLIC_BASE_URL: Optional[str] = ""
    LOCAL_SERVER_ENABLED: bool = False
    LOCAL_SERVER_HOST: str = "0.0.0.0"
    LOCAL_SERVER_PORT: int = 3018

    # =========================================================================
    # Automatic Media File Cleanup / TTL (Configurable)
    # =========================================================================
    MEDIA_CLEANUP_ENABLED: bool = True
    MEDIA_TTL_MINUTES: int = 120  # Delete files older than 120 minutes (2 hours)
    MEDIA_CLEANUP_INTERVAL_MINUTES: int = 30  # Run cleanup check every 30 minutes

    @property
    def allowed_users(self) -> List[int]:
        if not self.ALLOWED_USER_IDS:
            return []
        try:
            return [int(uid.strip()) for uid in self.ALLOWED_USER_IDS.split(",") if uid.strip()]
        except ValueError:
            return []

    # Helpers to resolve R2 / S3 credentials with seamless fallbacks
    @property
    def s3_or_r2_endpoint(self) -> Optional[str]:
        if self.S3_ENDPOINT_URL:
            return self.S3_ENDPOINT_URL
        if self.R2_ACCOUNT_ID:
            return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return None

    @property
    def s3_or_r2_access_key(self) -> Optional[str]:
        return self.R2_ACCESS_KEY_ID or self.S3_ACCESS_KEY_ID

    @property
    def s3_or_r2_secret_key(self) -> Optional[str]:
        return self.R2_SECRET_ACCESS_KEY or self.S3_SECRET_ACCESS_KEY

    @property
    def s3_or_r2_bucket(self) -> Optional[str]:
        return self.R2_BUCKET_NAME or self.S3_BUCKET_NAME

    @property
    def s3_or_r2_public_domain(self) -> Optional[str]:
        return self.R2_PUBLIC_DOMAIN or self.S3_PUBLIC_DOMAIN


settings = Settings()

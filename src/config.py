import os
from pathlib import Path
from typing import List, Optional, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve path strictly to ./config/.env relative to project layout
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_ENV_PATH = PROJECT_ROOT / "config" / ".env"

try:
    from dotenv import dotenv_values
    _file_env = dotenv_values(CONFIG_ENV_PATH) if CONFIG_ENV_PATH.is_file() else {}
except Exception:
    _file_env = {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CONFIG_ENV_PATH if CONFIG_ENV_PATH.is_file() else "config/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    BOT_TOKEN: str = ""
    ALLOWED_USER_IDS: Optional[str] = ""

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_and_fallback(cls, value: Any, info) -> Any:
        if isinstance(value, str):
            value = value.strip().strip("'\"")
        # If value is empty string or None (e.g. empty Docker env var), fallback to config/.env if available
        if (value is None or value == "") and info.field_name and _file_env:
            fallback_val = _file_env.get(info.field_name)
            if fallback_val is not None and fallback_val != "":
                if isinstance(fallback_val, str):
                    fallback_val = fallback_val.strip().strip("'\"")
                return fallback_val
        return value

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

    # =========================================================================
    # WhatsApp Chatbot Connector Settings
    # =========================================================================
    WHATSAPP_ENABLED: bool = False
    WHATSAPP_CONNECTOR_URL: str = "http://localhost:3019"
    WHATSAPP_DEFAULT_RECIPIENT: Optional[str] = ""

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

    def validate_storage_config(self) -> List[str]:
        """
        Validates only the variables relevant to the active STORAGE_TYPE.
        Returns a list of missing configuration variable names.
        """
        st = self.STORAGE_TYPE.lower().strip()
        missing = []
        if st == "r2":
            if not self.R2_ACCOUNT_ID:
                missing.append("R2_ACCOUNT_ID")
            if not self.R2_ACCESS_KEY_ID:
                missing.append("R2_ACCESS_KEY_ID")
            if not self.R2_SECRET_ACCESS_KEY:
                missing.append("R2_SECRET_ACCESS_KEY")
            if not self.R2_BUCKET_NAME:
                missing.append("R2_BUCKET_NAME")
            if not self.R2_PUBLIC_DOMAIN:
                missing.append("R2_PUBLIC_DOMAIN")
        elif st == "s3":
            if not self.S3_ACCESS_KEY_ID:
                missing.append("S3_ACCESS_KEY_ID")
            if not self.S3_SECRET_ACCESS_KEY:
                missing.append("S3_SECRET_ACCESS_KEY")
            if not self.S3_BUCKET_NAME:
                missing.append("S3_BUCKET_NAME")
        elif st == "local":
            if not self.LOCAL_PUBLIC_BASE_URL:
                missing.append("LOCAL_PUBLIC_BASE_URL")
        return missing

    def validate_required_config(self) -> List[str]:
        """
        Validates all strictly required variables for the active configuration.
        Returns a list of missing configuration variable names.
        """
        missing = []
        if not self.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not self.IG_USER_ID:
            missing.append("IG_USER_ID")
        if not self.IG_ACCESS_TOKEN:
            missing.append("IG_ACCESS_TOKEN")
        missing.extend(self.validate_storage_config())
        return missing


settings = Settings()

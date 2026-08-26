import os
from typing import List, Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    BOT_TOKEN: str
    ALLOWED_USER_IDS: Optional[str] = ""

    # Instagram
    IG_USER_ID: str
    IG_ACCESS_TOKEN: str
    IG_GRAPH_API_VERSION: str = "v21.0"

    # Gemini AI
    GEMINI_API_KEY: Optional[str] = ""

    # Storage Type: "s3", "r2", or "local"
    STORAGE_TYPE: str = "s3"

    # S3 / Cloudflare R2 Settings (if STORAGE_TYPE is "s3" or "r2")
    S3_ENDPOINT_URL: Optional[str] = ""
    S3_ACCESS_KEY_ID: Optional[str] = ""
    S3_SECRET_ACCESS_KEY: Optional[str] = ""
    S3_BUCKET_NAME: Optional[str] = ""
    S3_PUBLIC_DOMAIN: Optional[str] = ""

    # Local Storage Settings (if STORAGE_TYPE is "local")
    # Path where files will be stored on disk inside container/system
    LOCAL_STORAGE_DIR: str = "/app/data/media"
    # Public URL where the stored images can be accessed by Instagram API
    # Example: "https://media.mydomain.com" or "https://tunnel-id.trycloudflare.com"
    LOCAL_PUBLIC_BASE_URL: Optional[str] = ""
    # Whether to start built-in lightweight web server to serve LOCAL_STORAGE_DIR
    LOCAL_SERVER_ENABLED: bool = False
    LOCAL_SERVER_HOST: str = "0.0.0.0"
    LOCAL_SERVER_PORT: int = 3018

    @property
    def allowed_users(self) -> List[int]:
        if not self.ALLOWED_USER_IDS:
            return []
        try:
            return [int(uid.strip()) for uid in self.ALLOWED_USER_IDS.split(",") if uid.strip()]
        except ValueError:
            return []


settings = Settings()

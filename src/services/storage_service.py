import os
import uuid
import logging
from typing import Optional
import boto3
from botocore.client import Config
from src.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE.lower().strip()
        self.s3_client = None

        if self.storage_type in ("s3", "r2"):
            self._init_s3_client()
        elif self.storage_type == "local":
            logger.info(
                f"Configured LOCAL storage mode. Directory: '{settings.LOCAL_STORAGE_DIR}', "
                f"Public URL: '{settings.LOCAL_PUBLIC_BASE_URL}'"
            )
        else:
            logger.warning(
                f"Unknown STORAGE_TYPE '{settings.STORAGE_TYPE}'. Defaulting to local."
            )

    def _init_s3_client(self):
        if (
            settings.S3_ACCESS_KEY_ID
            and settings.S3_SECRET_ACCESS_KEY
            and settings.S3_BUCKET_NAME
        ):
            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
                "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
                "config": Config(signature_version="s3v4"),
            }
            if settings.S3_ENDPOINT_URL:
                client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

            try:
                self.s3_client = boto3.client(**client_kwargs)
                logger.info(f"Initialized S3 storage client for bucket '{settings.S3_BUCKET_NAME}'")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")

    async def upload_image(self, image_bytes: bytes, filename: Optional[str] = None) -> str:
        """
        Uploads/saves image according to STORAGE_TYPE and returns the public URL.
        """
        if not filename:
            filename = f"post_{uuid.uuid4().hex}.jpg"

        # Always save locally (either as primary storage or backup/cache)
        local_path = os.path.join(settings.LOCAL_STORAGE_DIR, filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(image_bytes)

        # 1. LOCAL STORAGE MODE
        if self.storage_type == "local":
            if not settings.LOCAL_PUBLIC_BASE_URL:
                raise ValueError(
                    "LOCAL_PUBLIC_BASE_URL is not set in .env! "
                    "Instagram Graph API requires a publicly accessible HTTPS/HTTP image_url. "
                    "Example: LOCAL_PUBLIC_BASE_URL=https://media.yourdomain.com"
                )
            
            public_base = settings.LOCAL_PUBLIC_BASE_URL.rstrip("/")
            public_url = f"{public_base}/{filename}"
            logger.info(f"Saved image to local storage: {local_path} -> Public URL: {public_url}")
            return public_url

        # 2. S3 / R2 STORAGE MODE
        if self.s3_client and settings.S3_BUCKET_NAME:
            try:
                self.s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=filename,
                    Body=image_bytes,
                    ContentType="image/jpeg",
                )

                if settings.S3_PUBLIC_DOMAIN:
                    public_domain = settings.S3_PUBLIC_DOMAIN.rstrip("/")
                    public_url = f"{public_domain}/{filename}"
                elif settings.S3_ENDPOINT_URL:
                    public_url = f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}/{filename}"
                else:
                    public_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{filename}"

                logger.info(f"Uploaded image to S3 bucket '{settings.S3_BUCKET_NAME}': {public_url}")
                return public_url
            except Exception as e:
                logger.error(f"S3 upload error: {e}")
                raise RuntimeError(f"Failed to upload media to S3: {e}")

        raise ValueError(
            f"STORAGE_TYPE is '{self.storage_type}', but S3 credentials/bucket are not properly configured in .env."
        )


storage_service = StorageService()

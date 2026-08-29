"""
Storage Service: handles media upload to Cloudflare R2, AWS S3, or Local Storage,
generating publicly accessible URLs required for Instagram Graph API publishing.
"""

import os
import uuid
import mimetypes
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
        endpoint = settings.s3_or_r2_endpoint
        access_key = settings.s3_or_r2_access_key
        secret_key = settings.s3_or_r2_secret_key
        bucket = settings.s3_or_r2_bucket

        if access_key and secret_key and bucket:
            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
                "config": Config(signature_version="s3v4"),
            }
            if endpoint:
                client_kwargs["endpoint_url"] = endpoint

            try:
                self.s3_client = boto3.client(**client_kwargs)
                service_label = "Cloudflare R2" if self.storage_type == "r2" or "r2.cloudflarestorage.com" in (endpoint or "") else "S3"
                logger.info(
                    f"Initialized {service_label} client. Bucket: '{bucket}', Endpoint: '{endpoint or 'AWS Default'}'"
                )
            except Exception as e:
                logger.error(f"Failed to initialize S3/R2 client: {e}")
        else:
            logger.warning("S3/R2 storage selected, but credentials or bucket name are incomplete.")

    async def upload_media(
        self,
        media_bytes: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        is_video: bool = False
    ) -> str:
        """
        Uploads image or video to public storage and returns the public HTTPS URL.
        """
        # Generate unique filename if not provided or if generic
        if not filename or filename in ("post_photo.jpg", "post_video.mp4", "image.jpg", "video.mp4"):
            ext = ".mp4" if is_video or (filename and filename.endswith(".mp4")) else ".jpg"
            filename = f"media_{uuid.uuid4().hex}{ext}"

        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = "video/mp4" if is_video or filename.endswith(".mp4") else "image/jpeg"

        # 1. LOCAL STORAGE MODE
        if self.storage_type == "local":
            local_path = os.path.join(settings.LOCAL_STORAGE_DIR, filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(media_bytes)

            if not settings.LOCAL_PUBLIC_BASE_URL:
                raise ValueError(
                    "LOCAL_PUBLIC_BASE_URL is not set! "
                    "Instagram Graph API requires a publicly accessible HTTPS URL. "
                    "Please provide LOCAL_PUBLIC_BASE_URL via Docker environment variable or in ./config/.env (e.g. LOCAL_PUBLIC_BASE_URL=https://media.yourdomain.com)"
                )
            
            public_base = settings.LOCAL_PUBLIC_BASE_URL.rstrip("/")
            public_url = f"{public_base}/{filename}"
            logger.info(f"Saved media to local storage: {local_path} -> Public URL: {public_url}")
            return public_url

        # 2. S3 / CLOUDFLARE R2 STORAGE MODE
        bucket = settings.s3_or_r2_bucket
        if self.s3_client and bucket:
            try:
                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=filename,
                    Body=media_bytes,
                    ContentType=content_type,
                )

                public_domain = settings.s3_or_r2_public_domain
                endpoint = settings.s3_or_r2_endpoint

                if public_domain:
                    public_url = f"{public_domain.rstrip('/')}/{filename}"
                elif endpoint:
                    public_url = f"{endpoint.rstrip('/')}/{bucket}/{filename}"
                else:
                    public_url = f"https://{bucket}.s3.amazonaws.com/{filename}"

                logger.info(f"Uploaded media to S3/R2 bucket '{bucket}': {public_url}")
                return public_url
            except Exception as e:
                logger.error(f"S3/R2 upload error: {e}")
                raise RuntimeError(f"Failed to upload media to S3/R2: {e}")

        if self.storage_type == "r2":
            raise ValueError(
                "STORAGE_TYPE is 'r2', but Cloudflare R2 credentials (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME) are incomplete in Docker environment or ./config/.env."
            )
        else:
            raise ValueError(
                "STORAGE_TYPE is 's3', but S3 credentials (S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, "
                "S3_BUCKET_NAME) are incomplete in Docker environment or ./config/.env."
            )

    async def upload_image(self, image_bytes: bytes, filename: Optional[str] = None) -> str:
        """
        Backwards-compatible wrapper for upload_media for images.
        """
        return await self.upload_media(image_bytes, filename=filename, is_video=False)


storage_service = StorageService()

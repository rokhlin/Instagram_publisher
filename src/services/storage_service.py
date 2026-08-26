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

        # 2. S3 / CLOUDFLARE R2 STORAGE MODE
        bucket = settings.s3_or_r2_bucket
        if self.s3_client and bucket:
            try:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = "image/jpeg"

                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=filename,
                    Body=image_bytes,
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

        raise ValueError(
            f"STORAGE_TYPE is '{self.storage_type}', but S3/R2 credentials or bucket name are missing in .env."
        )


storage_service = StorageService()

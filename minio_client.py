import json
import uuid
from io import BytesIO

from minio import Minio

from core.config import settings

client = Minio(
    endpoint=f"{settings.MINIO_ENDPOINT}:{settings.MINIO_PORT}",
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_USE_SSL,
)

BUCKET = settings.MINIO_BUCKET


def ensure_bucket() -> None:
    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)
    # Публичное чтение: SPA загружает картинки и видео напрямую из MinIO.
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{BUCKET}/*"],
            }
        ],
    }
    client.set_bucket_policy(BUCKET, json.dumps(policy))


def upload_file(file_bytes: bytes, original_name: str) -> str:
    ext = original_name.rsplit(".", 1)[-1] if "." in original_name else "bin"
    filename = f"{uuid.uuid4().hex}.{ext}"
    client.put_object(BUCKET, filename, BytesIO(file_bytes), len(file_bytes))
    return filename


def file_url(filename: str | None) -> str | None:
    """Имя файла из БД -> полный адрес в MinIO (старые записи уже хранят полный адрес)."""
    if not filename or filename.startswith(("http://", "https://")):
        return filename
    return f"{settings.MINIO_URL}/{BUCKET}/{filename}"

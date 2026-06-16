import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.core.config import settings

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def validate_file(file: UploadFile, allowed_types: list[str], max_mb: int = 5):
    """Validasi tipe dan ukuran file."""
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Format file tidak didukung. Gunakan: {', '.join(allowed_types)}"
        )
    content = await file.read()
    size_mb = len(content) / 1_000_000
    if size_mb > max_mb:
        raise HTTPException(
            status_code=413,
            detail=f"Ukuran file terlalu besar ({size_mb:.1f} MB). Maksimal {max_mb} MB."
        )
    await file.seek(0)
    return content


async def save_file(file: UploadFile, subfolder: str = "uploads") -> str:
    """
    Simpan file ke storage.
    Return URL publik file.
    """
    ext = Path(file.filename or "file").suffix or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_dir = UPLOAD_DIR / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    if settings.STORAGE_PROVIDER == "s3":
        return await _upload_s3(dest_path, subfolder, filename)

    return f"{settings.STORAGE_PUBLIC_BASE_URL}/uploads/{subfolder}/{filename}"


async def _upload_s3(local_path: Path, subfolder: str, filename: str) -> str:
    """Upload ke S3 / MinIO (opsional)."""
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            region_name=settings.STORAGE_REGION,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        )
        key = f"{subfolder}/{filename}"
        s3.upload_file(str(local_path), settings.STORAGE_BUCKET, key)
        local_path.unlink(missing_ok=True)
        return f"{settings.STORAGE_PUBLIC_BASE_URL}/{key}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload ke S3 gagal: {str(e)}")


def delete_file_by_url(url: str):
    """Hapus file lokal berdasarkan URL."""
    if not url:
        return
    try:
        relative = url.replace(f"{settings.STORAGE_PUBLIC_BASE_URL}/", "")
        path = Path("static") / relative
        if path.exists():
            path.unlink()
    except Exception:
        pass

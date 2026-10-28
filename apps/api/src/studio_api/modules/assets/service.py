from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from minio import Minio
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.assets.models import Asset, AssetDependency

ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "audio/wav",
    "video/mp4",
    "text/plain",
    "application/json",
    "application/zip",
}
MAX_BYTES = 500 * 1024 * 1024


def validate_media(content: bytes, declared_mime: str) -> dict[str, Any]:
    if declared_mime not in ALLOWED_MIME:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Unsupported media type")
    if len(content) > MAX_BYTES:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Asset exceeds 500 MB")
    metadata: dict[str, Any] = {}
    if declared_mime.startswith("image/"):
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
                width, height = image.size
                if width > 8192 or height > 8192:
                    raise StudioError(
                        ErrorCode.POLICY_REJECTED, "Image dimensions exceed 8192×8192"
                    )
                expected = "image/png" if image.format == "PNG" else "image/jpeg"
                if declared_mime != expected:
                    raise StudioError(
                        ErrorCode.POLICY_REJECTED, "Declared MIME does not match image data"
                    )
                metadata = {"width": width, "height": height}
        except UnidentifiedImageError as exc:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid image data") from exc
    elif declared_mime == "audio/wav" and not (content[:4] == b"RIFF" and content[8:12] == b"WAVE"):
        raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid WAV data")
    elif declared_mime == "video/mp4" and content[4:8] != b"ftyp":
        raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid MP4 data")
    elif declared_mime == "application/json":
        try:
            json.loads(content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid JSON data") from exc
    elif declared_mime == "text/plain":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid UTF-8 text") from exc
    return metadata


def _minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def read_asset(asset: Asset) -> bytes:
    settings = get_settings()
    if settings.asset_backend == "local":
        return secure_local_path(asset).read_bytes()

    def download() -> bytes:
        response = _minio_client().get_object(settings.minio_asset_bucket, asset.storage_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(download)


async def upload_asset(
    db: AsyncSession,
    workspace_id: UUID,
    content: bytes,
    mime_type: str,
    rights: dict[str, Any],
) -> Asset:
    metadata = validate_media(content, mime_type)
    digest = hashlib.sha256(content).hexdigest()
    existing = await db.scalar(
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.sha256 == digest)
    )
    if existing:
        return existing
    settings = get_settings()
    root = settings.local_asset_root.resolve()
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "audio/wav": ".wav",
        "video/mp4": ".mp4",
        "text/plain": ".txt",
        "application/json": ".json",
        "application/zip": ".zip",
    }[mime_type]
    relative = Path(str(workspace_id)) / digest[:2] / f"{digest}{extension}"
    if settings.asset_backend == "minio":
        await asyncio.to_thread(
            _minio_client().put_object,
            settings.minio_asset_bucket,
            str(relative),
            io.BytesIO(content),
            len(content),
            content_type=mime_type,
        )
    else:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    asset = Asset(
        workspace_id=workspace_id,
        sha256=digest,
        mime_type=mime_type,
        size_bytes=len(content),
        storage_key=str(relative),
        rights_declaration=rights,
        metadata_json=metadata,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def _descendants(db: AsyncSession, asset_id: UUID) -> set[UUID]:
    found: set[UUID] = set()
    frontier = {asset_id}
    while frontier:
        rows = set(
            await db.scalars(
                select(AssetDependency.output_asset_id).where(
                    AssetDependency.input_asset_id.in_(frontier)
                )
            )
        )
        frontier = rows - found
        found.update(rows)
    return found


async def record_dependency(
    db: AsyncSession,
    output_id: UUID,
    input_id: UUID,
    dependency_type: str,
    transform_run_id: str | None = None,
) -> AssetDependency:
    if output_id == input_id or input_id in await _descendants(db, output_id):
        raise StudioError(ErrorCode.POLICY_REJECTED, "Asset dependency would create a cycle")
    dependency = AssetDependency(
        output_asset_id=output_id,
        input_asset_id=input_id,
        dependency_type=dependency_type,
        transform_run_id=transform_run_id,
    )
    db.add(dependency)
    await db.commit()
    await db.refresh(dependency)
    return dependency


def secure_local_path(asset: Asset) -> Path:
    root = get_settings().local_asset_root.resolve()
    candidate = (root / asset.storage_key).resolve()
    if root not in candidate.parents:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid storage key")
    return candidate

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse
from uuid import UUID, uuid4

import httpx

from compose_ai_api.core.config import get_settings
from compose_ai_api.domains.exterior_design.constants import ALLOWED_IMAGE_MIME_TYPES


class AssetStorageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StoredAsset:
    storage_provider: str
    storage_key: str
    delivery_reference: str
    mime_type: str
    byte_size: int
    integrity_hash: str


class AssetStorage:
    provider = "local"

    async def store_image(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        option_id: UUID,
        content: bytes,
        mime_type: str,
    ) -> StoredAsset: ...

    async def exists(self, storage_key: str) -> bool: ...

    async def read(self, storage_key: str) -> bytes: ...

    async def soft_delete(self, storage_key: str) -> None: ...

    async def health_check(self) -> bool: ...


class LocalAssetStorage(AssetStorage):
    provider = "local"

    def __init__(self, *, root: Path, public_base_url: str, max_image_bytes: int) -> None:
        self.root = root.resolve()
        self.public_base_url = public_base_url.rstrip("/")
        self.max_image_bytes = max_image_bytes

    async def store_image(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        option_id: UUID,
        content: bytes,
        mime_type: str,
    ) -> StoredAsset:
        _validate_image_content(content, mime_type, self.max_image_bytes)
        extension = _extension_for_mime(mime_type)
        digest = hashlib.sha256(content).hexdigest()
        storage_key = str(
            PurePosixPath(
                "exterior-design",
                str(organization_id),
                str(project_id),
                str(option_id),
                f"{uuid4().hex}.{extension}",
            )
        )
        destination = self._path_for_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredAsset(
            storage_provider=self.provider,
            storage_key=storage_key,
            delivery_reference=f"{self.public_base_url}/{storage_key}",
            mime_type=mime_type,
            byte_size=len(content),
            integrity_hash=digest,
        )

    async def exists(self, storage_key: str) -> bool:
        return self._path_for_key(storage_key).exists()

    async def read(self, storage_key: str) -> bytes:
        path = self._path_for_key(storage_key)
        if not path.exists():
            raise AssetStorageError("ASSET_NOT_FOUND", "Generated asset was not found.")
        return path.read_bytes()

    async def soft_delete(self, storage_key: str) -> None:
        path = self._path_for_key(storage_key)
        if path.exists():
            deleted_path = path.with_suffix(path.suffix + ".deleted")
            path.replace(deleted_path)

    async def health_check(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            return self.root.exists() and self.root.is_dir()
        except OSError:
            return False

    def _path_for_key(self, storage_key: str) -> Path:
        normalized = PurePosixPath(storage_key)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise AssetStorageError("ASSET_PATH_INVALID", "Invalid asset storage key.")
        target = (self.root / Path(*normalized.parts)).resolve()
        if self.root not in target.parents and target != self.root:
            raise AssetStorageError("ASSET_PATH_INVALID", "Invalid asset storage key.")
        return target


class S3CompatibleAssetStorage(AssetStorage):
    provider = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None,
        public_base_url: str,
        prefix: str,
        max_image_bytes: int,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url.rstrip("/") if endpoint_url else None
        self.public_base_url = public_base_url.rstrip("/")
        self.prefix = prefix.strip("/")
        self.max_image_bytes = max_image_bytes

    async def store_image(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        option_id: UUID,
        content: bytes,
        mime_type: str,
    ) -> StoredAsset:
        _validate_image_content(content, mime_type, self.max_image_bytes)
        extension = _extension_for_mime(mime_type)
        digest = hashlib.sha256(content).hexdigest()
        storage_key = str(
            PurePosixPath(
                self.prefix,
                "exterior-design",
                str(organization_id),
                str(project_id),
                str(option_id),
                f"{uuid4().hex}.{extension}",
            )
        )
        await self._request(
            "PUT",
            storage_key,
            content=content,
            content_type=mime_type,
            expected_status={200},
        )
        return StoredAsset(
            storage_provider=self.provider,
            storage_key=storage_key,
            delivery_reference=f"{self.public_base_url}/{storage_key}",
            mime_type=mime_type,
            byte_size=len(content),
            integrity_hash=digest,
        )

    async def exists(self, storage_key: str) -> bool:
        try:
            response = await self._request("HEAD", storage_key, expected_status={200, 404})
        except AssetStorageError:
            return False
        return response.status_code == 200

    async def read(self, storage_key: str) -> bytes:
        response = await self._request("GET", storage_key, expected_status={200})
        return response.content

    async def soft_delete(self, storage_key: str) -> None:
        await self._request("DELETE", storage_key, expected_status={204, 404})

    async def health_check(self) -> bool:
        try:
            await self._request("HEAD", "", expected_status={200, 403, 404})
        except AssetStorageError:
            return False
        return True

    async def _request(
        self,
        method: str,
        storage_key: str,
        *,
        content: bytes = b"",
        content_type: str | None = None,
        expected_status: set[int],
    ) -> httpx.Response:
        url, canonical_uri, host = self._object_url(storage_key)
        headers = self._signed_headers(
            method,
            canonical_uri,
            host,
            content,
            content_type=content_type,
        )
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, url, content=content, headers=headers)
        if response.status_code not in expected_status:
            raise AssetStorageError(
                "ASSET_STORAGE_UNAVAILABLE",
                "Object storage request failed.",
            )
        return response

    def _object_url(self, storage_key: str) -> tuple[str, str, str]:
        if storage_key:
            normalized = PurePosixPath(storage_key)
            if normalized.is_absolute() or ".." in normalized.parts:
                raise AssetStorageError("ASSET_PATH_INVALID", "Invalid asset storage key.")
            key_path = "/".join(quote(part, safe="") for part in normalized.parts)
        else:
            key_path = ""
        if self.endpoint_url:
            parsed = urlparse(self.endpoint_url)
            base_path = parsed.path.rstrip("/")
            canonical_uri = f"{base_path}/{self.bucket}/{key_path}".rstrip("/")
            url = f"{parsed.scheme}://{parsed.netloc}{canonical_uri}"
            return url, canonical_uri or "/", parsed.netloc
        host = f"{self.bucket}.s3.{self.region}.amazonaws.com"
        canonical_uri = f"/{key_path}" if key_path else "/"
        return f"https://{host}{canonical_uri}", canonical_uri, host

    def _signed_headers(
        self,
        method: str,
        canonical_uri: str,
        host: str,
        content: bytes,
        *,
        content_type: str | None,
    ) -> dict[str, str]:
        now = dt.datetime.now(dt.UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = {
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            headers["content-type"] = content_type
        signed_header_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
        canonical_request = "\n".join(
            [method, canonical_uri, "", canonical_headers, signed_header_names, payload_hash]
        )
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _signing_key(self.secret_access_key, date_stamp, self.region),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers["authorization"] = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_header_names}, Signature={signature}"
        )
        return headers


def create_asset_storage() -> AssetStorage:
    settings = get_settings()
    if settings.asset_storage_provider == "local":
        root = Path(settings.asset_storage_local_root or ".compose-assets")
        return LocalAssetStorage(
            root=root,
            public_base_url=settings.asset_public_base_url or "/api/v1/assets",
            max_image_bytes=settings.asset_max_image_bytes,
        )
    if settings.asset_storage_provider in {"s3", "r2"}:
        required = {
            "bucket": settings.asset_storage_s3_bucket,
            "accessKeyId": settings.asset_storage_s3_access_key_id,
            "secretAccessKey": settings.asset_storage_s3_secret_access_key,
            "publicBaseUrl": settings.asset_storage_s3_public_base_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise AssetStorageError(
                "ASSET_STORAGE_NOT_CONFIGURED",
                "Object storage is missing required configuration.",
            )
        return S3CompatibleAssetStorage(
            bucket=str(settings.asset_storage_s3_bucket),
            region=settings.asset_storage_s3_region,
            access_key_id=str(settings.asset_storage_s3_access_key_id),
            secret_access_key=str(settings.asset_storage_s3_secret_access_key),
            endpoint_url=settings.asset_storage_s3_endpoint_url,
            public_base_url=str(settings.asset_storage_s3_public_base_url),
            prefix=settings.asset_storage_prefix,
            max_image_bytes=settings.asset_max_image_bytes,
        )
    raise AssetStorageError(
        "ASSET_STORAGE_UNSUPPORTED",
        "Configured asset storage provider is not supported in this environment.",
    )


def _validate_image_content(content: bytes, mime_type: str, max_image_bytes: int) -> None:
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise AssetStorageError(
            "ASSET_MIME_UNSUPPORTED", "Generated image MIME type is not supported."
        )
    if not content:
        raise AssetStorageError("ASSET_EMPTY", "Generated image content is empty.")
    if len(content) > max_image_bytes:
        raise AssetStorageError(
            "ASSET_TOO_LARGE", "Generated image exceeds the configured size limit."
        )


def _extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }[mime_type]


def _signing_key(secret_access_key: str, date_stamp: str, region: str) -> bytes:
    date_key = _sign(("AWS4" + secret_access_key).encode("utf-8"), date_stamp)
    date_region_key = _sign(date_key, region)
    date_region_service_key = _sign(date_region_key, "s3")
    return _sign(date_region_service_key, "aws4_request")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

from __future__ import annotations

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import anyio
import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from .object_config import ObjectAccessSettings
from .objects import ObjectRecord


class ObjectStoreError(Exception):
    def __init__(self, code: str, status_code: int = 502):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class PresignedRequest:
    method: str
    url: str
    headers: dict[str, str]
    expires_in_seconds: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "expires_in_seconds": self.expires_in_seconds,
        }


@dataclass(frozen=True, slots=True)
class VerifiedObject:
    size_bytes: int
    sha256: str


class S3ObjectStore:
    """Private RustFS adapter with public signing and internal verification.

    Upload and download URLs are signed against the public endpoint. Integrity
    verification and physical deletion use the Compose-internal endpoint so the
    gateway never trusts a client-supplied completion result.
    """

    def __init__(self, settings: ObjectAccessSettings):
        self.bucket = settings.rustfs_private_bucket
        self.expires_in_seconds = settings.object_presign_ttl_seconds
        self.max_size_bytes = settings.object_max_size_bytes
        credentials = {
            "aws_access_key_id": settings.rustfs_access_key.get_secret_value(),
            "aws_secret_access_key": settings.rustfs_secret_key.get_secret_value(),
            "region_name": settings.rustfs_region,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        self._internal = boto3.client(
            "s3",
            endpoint_url=settings.rustfs_internal_endpoint,
            **credentials,
        )
        self._public = boto3.client(
            "s3",
            endpoint_url=settings.rustfs_public_endpoint,
            **credentials,
        )

    async def create_upload(self, record: ObjectRecord) -> PresignedRequest:
        if record.state != "reserved":
            raise ObjectStoreError("object_upload_not_reserved", status_code=409)
        return await anyio.to_thread.run_sync(self._create_upload_sync, record)

    async def verify_upload(self, record: ObjectRecord) -> VerifiedObject:
        if record.state != "reserved":
            raise ObjectStoreError("object_upload_not_reserved", status_code=409)
        return await anyio.to_thread.run_sync(self._verify_upload_sync, record)

    async def create_download(self, record: ObjectRecord) -> PresignedRequest:
        if record.state != "ready":
            raise ObjectStoreError("object_not_ready", status_code=409)
        return await anyio.to_thread.run_sync(self._create_download_sync, record)

    async def delete(self, record: ObjectRecord) -> None:
        await anyio.to_thread.run_sync(self._delete_sync, record)

    def _create_upload_sync(self, record: ObjectRecord) -> PresignedRequest:
        try:
            url = self._public.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": record.object_key,
                    "ContentType": record.content_type,
                },
                ExpiresIn=self.expires_in_seconds,
                HttpMethod="PUT",
            )
        except (BotoCoreError, ClientError, ValueError) as exc:
            raise self._translate_error(exc, "object_upload_sign_failed") from exc
        return PresignedRequest(
            method="PUT",
            url=url,
            headers={"Content-Type": record.content_type},
            expires_in_seconds=self.expires_in_seconds,
        )

    def _verify_upload_sync(self, record: ObjectRecord) -> VerifiedObject:
        body: Any = None
        try:
            response = self._internal.get_object(
                Bucket=self.bucket,
                Key=record.object_key,
            )
            reported_size = int(response.get("ContentLength") or 0)
            if reported_size != record.size_bytes:
                self._delete_quiet(record)
                raise ObjectStoreError("object_size_mismatch", status_code=409)
            body = response["Body"]
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > record.size_bytes or total > self.max_size_bytes:
                    self._delete_quiet(record)
                    raise ObjectStoreError("object_size_mismatch", status_code=409)
                digest.update(chunk)
            actual_sha256 = digest.hexdigest()
            if total != record.size_bytes:
                self._delete_quiet(record)
                raise ObjectStoreError("object_size_mismatch", status_code=409)
            if actual_sha256 != record.sha256:
                self._delete_quiet(record)
                raise ObjectStoreError("object_sha256_mismatch", status_code=409)
            return VerifiedObject(size_bytes=total, sha256=actual_sha256)
        except ObjectStoreError:
            raise
        except (BotoCoreError, ClientError, KeyError, TypeError, ValueError) as exc:
            raise self._translate_error(exc, "object_verify_failed") from exc
        finally:
            if body is not None:
                with suppress(Exception):
                    body.close()

    def _create_download_sync(self, record: ObjectRecord) -> PresignedRequest:
        try:
            self._internal.head_object(Bucket=self.bucket, Key=record.object_key)
            disposition = (
                "attachment; filename*=UTF-8''" + quote(record.original_name, safe="")
            )
            url = self._public.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": record.object_key,
                    "ResponseContentType": record.content_type,
                    "ResponseContentDisposition": disposition,
                },
                ExpiresIn=self.expires_in_seconds,
                HttpMethod="GET",
            )
        except (BotoCoreError, ClientError, ValueError) as exc:
            raise self._translate_error(exc, "object_download_sign_failed") from exc
        return PresignedRequest(
            method="GET",
            url=url,
            headers={},
            expires_in_seconds=self.expires_in_seconds,
        )

    def _delete_sync(self, record: ObjectRecord) -> None:
        try:
            self._internal.delete_object(Bucket=self.bucket, Key=record.object_key)
        except ClientError as exc:
            status = int(
                (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode") or 0
            )
            if status == 404:
                return
            raise self._translate_error(exc, "object_delete_failed") from exc
        except BotoCoreError as exc:
            raise self._translate_error(exc, "object_delete_failed") from exc

    def _delete_quiet(self, record: ObjectRecord) -> None:
        with suppress(BotoCoreError, ClientError):
            self._internal.delete_object(Bucket=self.bucket, Key=record.object_key)

    @staticmethod
    def _translate_error(exc: Exception, fallback: str) -> ObjectStoreError:
        if isinstance(exc, ClientError):
            status = int(
                (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode") or 0
            )
            code = str((exc.response.get("Error") or {}).get("Code") or "").lower()
            if status == 404 or code in {"nosuchkey", "notfound", "nosuchbucket"}:
                return ObjectStoreError("object_blob_not_found", status_code=404)
            if status in {401, 403}:
                return ObjectStoreError("object_store_access_denied", status_code=503)
            if status == 429:
                return ObjectStoreError("object_store_rate_limited", status_code=503)
        return ObjectStoreError(fallback, status_code=503)

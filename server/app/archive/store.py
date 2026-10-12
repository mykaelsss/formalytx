"""Byte storage for the session archive.

The archive only needs get and put by key, so moving to another backend means
adding one class here.
"""

import os
import tempfile
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class BlobStore(Protocol):
    def get(self, key: str) -> bytes | None:
        """The object's bytes, or None when it doesn't exist."""
        ...

    def put(self, key: str, data: bytes, content_type: str) -> None: ...


class LocalBlobStore:
    """Objects as files under a directory. For development and tests."""

    def __init__(self, root: str):
        self._root = os.path.abspath(root)

    def _path(self, key: str) -> str:
        path = os.path.abspath(os.path.join(self._root, key))
        if not path.startswith(self._root + os.sep):
            raise ValueError(f"Key escapes the store root: {key!r}")
        return path

    def get(self, key: str) -> bytes | None:
        try:
            with open(self._path(key), "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Write then rename so a reader never sees a partial object.
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            # mkstemp creates the file owner-only; match a normally created file.
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


class R2BlobStore:
    """Objects in a Cloudflare R2 bucket, through its S3-compatible API."""

    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str, bucket: str, client=None):
        self._bucket = bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(
                # Uploads run on a thread pool; one connection per worker.
                max_pool_connections=32,
                retries={"max_attempts": 5, "mode": "standard"},
                connect_timeout=10,
                read_timeout=30,
                # R2 doesn't support every checksum newer boto3 sends by default.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def get(self, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return response["Body"].read()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

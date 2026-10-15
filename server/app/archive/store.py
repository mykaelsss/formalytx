"""Byte storage for the session archive.

The archive only needs get and put by key, and the MD5 of what's stored under
a prefix, so moving to another backend means adding one class here.
"""

import hashlib
import os
import socket
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

    def digests(self, prefix: str) -> dict[str, str]:
        """The MD5 hex digest of each object whose key starts with prefix."""
        ...


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

    def digests(self, prefix: str) -> dict[str, str]:
        # A prefix can end partway through a name, so walk its parent folder.
        folder = os.path.dirname(self._path(prefix + "_"))
        found = {}
        for root, _dirs, files in os.walk(folder):
            for name in files:
                if name.startswith(".tmp-"):
                    continue
                path = os.path.join(root, name)
                key = os.path.relpath(path, self._root).replace(os.sep, "/")
                if key.startswith(prefix):
                    with open(path, "rb") as f:
                        found[key] = hashlib.md5(f.read()).hexdigest()
        return found


# Somewhere between the API and R2, a connection left idle for some minutes is
# dropped without either end hearing about it: a request sent on it later gets
# no reply, not even a reset. TCP keepalive probes keep pooled connections from
# going idle, and if one is dropped anyway, the failed probes close it before
# the pool hands it out. The kernel's default waits two hours before probing.
KEEPALIVE_IDLE_SECONDS = 60
KEEPALIVE_INTERVAL_SECONDS = 10
KEEPALIVE_PROBES = 3
# Linux calls the idle time TCP_KEEPIDLE, macOS TCP_KEEPALIVE.
_TCP_KEEPIDLE = getattr(socket, "TCP_KEEPIDLE", None) or getattr(socket, "TCP_KEEPALIVE")
KEEPALIVE_SOCKET_OPTIONS = [
    (socket.IPPROTO_TCP, _TCP_KEEPIDLE, KEEPALIVE_IDLE_SECONDS),
    (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, KEEPALIVE_INTERVAL_SECONDS),
    (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, KEEPALIVE_PROBES),
]

# Should a request still go out on a dropped connection, it waits out the read
# timeout before botocore retries on a new one. Archive objects are small and
# R2 serves them in well under a second, so reads give up quickly.
READ_TIMEOUT_SECONDS = 5
# Uploads and listings keep a longer timeout: an export uploads many objects at
# once, possibly over a slow link.
WRITE_TIMEOUT_SECONDS = 30


def _r2_client(account_id: str, access_key_id: str, secret_access_key: str, read_timeout: float):
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
        config=Config(
            # Reads and uploads run on thread pools; one connection per worker.
            max_pool_connections=32,
            retries={"max_attempts": 5, "mode": "standard"},
            connect_timeout=10,
            read_timeout=read_timeout,
            tcp_keepalive=True,
            # R2 doesn't support every checksum newer boto3 sends by default.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
    # botocore only turns keepalive on, leaving its timing to the kernel, and
    # has no option for it. Its HTTP session hands this list of socket options
    # to every connection it opens, so add the timing to it.
    client._endpoint.http_session._socket_options.extend(KEEPALIVE_SOCKET_OPTIONS)
    return client


class R2BlobStore:
    """Objects in a Cloudflare R2 bucket, through its S3-compatible API."""

    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str, bucket: str, client=None):
        self._bucket = bucket
        if client is not None:
            self._reads = self._writes = client
        else:
            credentials = (account_id, access_key_id, secret_access_key)
            self._reads = _r2_client(*credentials, read_timeout=READ_TIMEOUT_SECONDS)
            self._writes = _r2_client(*credentials, read_timeout=WRITE_TIMEOUT_SECONDS)

    def get(self, key: str) -> bytes | None:
        try:
            response = self._reads.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return response["Body"].read()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._writes.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def digests(self, prefix: str) -> dict[str, str]:
        # R2's ETag of an object uploaded in one part is its MD5.
        found = {}
        for page in self._writes.get_paginator("list_objects_v2").paginate(Bucket=self._bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                found[item["Key"]] = item["ETag"].strip('"')
        return found

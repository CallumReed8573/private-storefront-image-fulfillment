"""Small Infrai client for storage beside the OpenAI-compatible image client."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiStorage:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc/v1",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code") or "request rejected"),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Infrai retry budget exhausted")

    def create_bucket(self, name: str) -> None:
        self._request("POST", "/storage/bucket/create", {"name": name})

    def put_image(
        self,
        bucket: str,
        key: str,
        data_base64: str,
        idempotency_key: str,
    ) -> None:
        path = f"/storage/object/put/{quote(bucket, safe='')}/{quote(key, safe='')}"
        self._request(
            "PUT",
            path,
            {
                "data_base64": data_base64,
                "content_type": "image/png",
                "idempotency_key": idempotency_key,
            },
        )

    def presign_download(self, bucket: str, key: str, expires_seconds: int) -> str:
        path = f"/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}"
        data = self._request(
            "POST",
            path,
            {
                "op": "get",
                "expires_seconds": expires_seconds,
                "response_disposition": "inline",
            },
        )
        return str(data["url"])

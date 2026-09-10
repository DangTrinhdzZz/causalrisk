"""Minimal JSON-over-HTTP transport with no implicit retries or secret logging."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPResponse
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from causalrisk.retry import ClassifiedFailure

MAX_RESPONSE_BYTES = 10_000_000


@dataclass(frozen=True, slots=True)
class JsonHttpResponse:
    status: int
    headers: dict[str, str]
    document: dict[str, Any]


class JsonHttpTransport(Protocol):
    """One HTTP attempt. Retry decisions belong to the project wrapper."""

    def post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> JsonHttpResponse:
        """POST one JSON document and return one decoded JSON object."""


def _retry_after_seconds(value: str | None, *, now: datetime | None = None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            current = now or datetime.now(UTC)
            return max(0.0, (retry_at - current).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, seconds)


def classify_http_status(status: int, retry_after: str | None = None) -> ClassifiedFailure:
    """Map a provider HTTP status to the frozen failure taxonomy."""

    if status in {401, 403}:
        code = "configuration/authentication"
    elif status == 404:
        code = "configuration/nonexistent_model"
    elif status == 402:
        code = "configuration/quota_exhaustion"
    elif status in {400, 405, 409, 415, 422}:
        code = "configuration/malformed_request"
    elif status in {408, 504}:
        code = "transport/timeout"
    elif status == 429:
        code = "provider/http_429"
    elif 500 <= status <= 599:
        code = "provider/http_5xx"
    else:
        code = "provider/http_error"
    return ClassifiedFailure(
        code,
        f"provider returned HTTP {status}",
        http_status=status,
        retry_after_seconds=_retry_after_seconds(retry_after),
    )


@dataclass(slots=True)
class StdlibJsonHttpTransport:
    """Synchronous standard-library transport that performs exactly one attempt."""

    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> JsonHttpResponse:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request_headers = {"Accept": "application/json", "Content-Type": "application/json", **headers}
        request = Request(url, data=body, headers=request_headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed HTTPS provider URLs
                return self._decode_response(response)
        except HTTPError as error:
            retry_after = error.headers.get("Retry-After") if error.headers is not None else None
            status = error.code
            error.close()
            raise classify_http_status(status, retry_after) from None
        except TimeoutError:
            raise ClassifiedFailure("transport/timeout", "provider request timed out") from None
        except (URLError, OSError):
            raise ClassifiedFailure("transport", "provider connection failed") from None

    @staticmethod
    def _decode_response(response: HTTPResponse) -> JsonHttpResponse:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ClassifiedFailure("response/schema_failure", "provider response exceeded the safe size limit")
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ClassifiedFailure("response/schema_failure", "provider returned invalid JSON") from error
        if not isinstance(document, dict):
            raise ClassifiedFailure("response/schema_failure", "provider JSON root is not an object")
        return JsonHttpResponse(
            status=int(response.status),
            headers={str(key).lower(): str(value) for key, value in response.headers.items()},
            document=document,
        )

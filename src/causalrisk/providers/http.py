"""Minimal JSON-over-HTTP transport with no implicit retries or secret logging."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPResponse
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from causalrisk.retry import ClassifiedFailure

MAX_RESPONSE_BYTES = 10_000_000
MAX_ERROR_RESPONSE_BYTES = 131_072
SAFE_PROVIDER_ERROR_FIELD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DEFAULT_USER_AGENT = "causalrisk-provider-client/1.0"


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


def _safe_provider_error_field(value: Any) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not SAFE_PROVIDER_ERROR_FIELD.fullmatch(value):
        return None
    if value.startswith(("sk-", "gsk_", "nvapi-", "AIza")):
        return None
    return value


def extract_provider_error_metadata(raw: bytes) -> tuple[str | None, str | None, str | None]:
    """Extract only code/type/param fields; never retain a provider message."""

    if len(raw) > MAX_ERROR_RESPONSE_BYTES:
        return None, None, None
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None, None
    if not isinstance(document, dict):
        return None, None, None
    error = document.get("error")
    if not isinstance(error, dict):
        errors = document.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            error = errors[0]
        else:
            return None, None, None
    error_code = _safe_provider_error_field(error.get("code") or error.get("status"))
    error_type = _safe_provider_error_field(error.get("type") or error.get("status"))
    error_param = _safe_provider_error_field(error.get("param"))
    return error_code, error_type, error_param


def classify_http_status(
    status: int,
    retry_after: str | None = None,
    *,
    provider_error_code: str | None = None,
    provider_error_type: str | None = None,
    provider_error_param: str | None = None,
) -> ClassifiedFailure:
    """Map a provider HTTP status to the frozen failure taxonomy."""

    normalized_code = (provider_error_code or "").lower()
    if normalized_code in {"insufficient_quota", "quota_exceeded", "billing_hard_limit_reached"}:
        code = "configuration/quota_exhaustion"
    elif normalized_code in {"model_not_found", "unknown_model"}:
        code = "configuration/nonexistent_model"
    elif status in {401, 403}:
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
        provider_error_code=provider_error_code,
        provider_error_type=provider_error_type,
        provider_error_param=provider_error_param,
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
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
            **headers,
        }
        request = Request(url, data=body, headers=request_headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed HTTPS provider URLs
                return self._decode_response(response)
        except HTTPError as error:
            retry_after = error.headers.get("Retry-After") if error.headers is not None else None
            status = error.code
            error_metadata = extract_provider_error_metadata(error.read(MAX_ERROR_RESPONSE_BYTES + 1))
            error.close()
            raise classify_http_status(
                status,
                retry_after,
                provider_error_code=error_metadata[0],
                provider_error_type=error_metadata[1],
                provider_error_param=error_metadata[2],
            ) from None
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

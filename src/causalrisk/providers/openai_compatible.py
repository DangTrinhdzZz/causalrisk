"""Adapters for explicit OpenAI-compatible chat-completions endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from causalrisk.credentials import SecretValue
from causalrisk.providers._response import (
    as_mapping,
    as_sequence,
    chat_content_text,
    optional_string,
    optional_token,
    schema_failure,
)
from causalrisk.providers.base import ProviderRequest, ProviderResponse
from causalrisk.providers.http import JsonHttpTransport, StdlibJsonHttpTransport
from causalrisk.retry import ClassifiedFailure
from causalrisk.usage import TokenUsage


@dataclass(slots=True)
class OpenAICompatibleChatAdapter:
    """One-call adapter for a declared OpenAI-compatible provider endpoint."""

    name: str
    credential_environment_variable: str
    credential: SecretValue
    endpoint: str
    max_tokens_field: str = "max_tokens"
    seed_field: str | None = None
    transport: JsonHttpTransport = field(default_factory=StdlibJsonHttpTransport)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": request.model_id,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            self.max_tokens_field: request.max_output_tokens,
            "stream": False,
        }
        if request.seed is not None:
            if self.seed_field is None:
                raise ClassifiedFailure(
                    "configuration/malformed_request",
                    f"seed is not supported by the frozen {self.name} adapter",
                )
            payload[self.seed_field] = request.seed

        started = perf_counter()
        response = self.transport.post(
            self.endpoint,
            {"Authorization": f"Bearer {self.credential.get_secret_value()}"},
            payload,
        )
        latency_ms = (perf_counter() - started) * 1000
        document = response.document
        choices = as_sequence(document.get("choices"), "choices is missing or invalid")
        if not choices:
            raise schema_failure("choices is empty")
        choice = as_mapping(choices[0], "first choice is not an object")
        finish_reason = optional_string(choice.get("finish_reason"))
        if finish_reason in {"length", "max_tokens"}:
            raise ClassifiedFailure(
                "configuration/output_cap_truncation",
                "provider stopped at the configured output cap",
                http_status=response.status,
            )
        if finish_reason in {"content_filter", "safety"}:
            raise ClassifiedFailure(
                "response/safety_refusal",
                "provider blocked the response for safety",
                http_status=response.status,
            )
        message = as_mapping(choice.get("message"), "choice message is missing or invalid")
        if optional_string(message.get("refusal")) is not None:
            raise ClassifiedFailure(
                "response/safety_refusal",
                "provider returned a safety refusal",
                http_status=response.status,
            )
        text = chat_content_text(message.get("content"))
        usage_value = document.get("usage")
        usage = as_mapping(usage_value, "usage is missing or invalid") if usage_value is not None else {}
        return ProviderResponse(
            provider=self.name,
            requested_model_id=request.model_id,
            reported_model_id=optional_string(document.get("model")),
            text=text,
            usage=TokenUsage(
                optional_token(usage.get("prompt_tokens"), "prompt_tokens is invalid"),
                optional_token(usage.get("completion_tokens"), "completion_tokens is invalid"),
                f"{self.name}_reported_usage",
            ),
            latency_ms=latency_ms,
            response_id=optional_string(document.get("id")),
            http_status=response.status,
        )

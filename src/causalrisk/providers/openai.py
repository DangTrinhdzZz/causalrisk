"""Direct OpenAI Responses API adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from causalrisk.credentials import SecretValue
from causalrisk.providers._response import (
    as_mapping,
    as_sequence,
    optional_string,
    optional_token,
    schema_failure,
)
from causalrisk.providers.base import ProviderRequest, ProviderResponse
from causalrisk.providers.http import JsonHttpTransport, StdlibJsonHttpTransport
from causalrisk.retry import ClassifiedFailure
from causalrisk.usage import TokenUsage

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"


@dataclass(slots=True)
class OpenAIResponsesAdapter:
    credential: SecretValue
    transport: JsonHttpTransport = field(default_factory=StdlibJsonHttpTransport)
    name: str = field(init=False, default="openai")
    credential_environment_variable: str = field(init=False, default="OPENAI_API_KEY")

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        if request.seed is not None:
            raise ClassifiedFailure(
                "configuration/malformed_request",
                "seed is not supported by the frozen OpenAI Responses adapter",
            )
        payload: dict[str, Any] = {
            "model": request.model_id,
            "input": request.prompt,
            "max_output_tokens": request.max_output_tokens,
            "store": False,
        }
        started = perf_counter()
        response = self.transport.post(
            OPENAI_RESPONSES_ENDPOINT,
            {"Authorization": f"Bearer {self.credential.get_secret_value()}"},
            payload,
        )
        latency_ms = (perf_counter() - started) * 1000
        document = response.document
        self._check_terminal_status(document, response.status)
        text = self._output_text(document, response.status)
        usage_value = document.get("usage")
        usage = as_mapping(usage_value, "usage is missing or invalid") if usage_value is not None else {}
        return ProviderResponse(
            provider=self.name,
            requested_model_id=request.model_id,
            reported_model_id=optional_string(document.get("model")),
            text=text,
            usage=TokenUsage(
                optional_token(usage.get("input_tokens"), "input_tokens is invalid"),
                optional_token(usage.get("output_tokens"), "output_tokens is invalid"),
                "openai_responses_reported_usage",
            ),
            latency_ms=latency_ms,
            response_id=optional_string(document.get("id")),
            http_status=response.status,
        )

    @staticmethod
    def _check_terminal_status(document: dict[str, Any], http_status: int) -> None:
        status = optional_string(document.get("status"))
        if status == "incomplete":
            details_value = document.get("incomplete_details")
            details = as_mapping(details_value, "incomplete_details is missing")
            reason = optional_string(details.get("reason"))
            if reason in {"max_output_tokens", "max_tokens"}:
                raise ClassifiedFailure(
                    "configuration/output_cap_truncation",
                    "OpenAI response stopped at the configured output cap",
                    http_status=http_status,
                )
            raise schema_failure("OpenAI response is incomplete for an unknown reason")
        if status not in {None, "completed"}:
            raise schema_failure("OpenAI response has an unexpected terminal status")

    @staticmethod
    def _output_text(document: dict[str, Any], http_status: int) -> str:
        direct_text = document.get("output_text")
        if isinstance(direct_text, str) and direct_text:
            return direct_text
        output = as_sequence(document.get("output"), "output is missing or invalid")
        texts: list[str] = []
        for item_value in output:
            item = as_mapping(item_value, "output item is not an object")
            content_value = item.get("content")
            if content_value is None:
                continue
            for part_value in as_sequence(content_value, "output content is not a list"):
                part = as_mapping(part_value, "output content part is not an object")
                part_type = optional_string(part.get("type"))
                if part_type == "refusal":
                    raise ClassifiedFailure(
                        "response/safety_refusal",
                        "OpenAI returned a safety refusal",
                        http_status=http_status,
                    )
                if part_type == "output_text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
        if not texts:
            raise schema_failure("OpenAI response contains no output text")
        return "\n".join(texts)

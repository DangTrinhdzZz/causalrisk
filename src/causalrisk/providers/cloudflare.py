"""Cloudflare Workers AI REST adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from urllib.parse import quote

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

CLOUDFLARE_API_ROOT = "https://api.cloudflare.com/client/v4/accounts"


@dataclass(slots=True)
class CloudflareWorkersAIAdapter:
    credential: SecretValue
    account_id: SecretValue
    transport: JsonHttpTransport = field(default_factory=StdlibJsonHttpTransport)
    name: str = field(init=False, default="cloudflare_workers_ai")
    credential_environment_variable: str = field(init=False, default="CLOUDFLARE_API_TOKEN")
    account_environment_variable: str = field(init=False, default="CLOUDFLARE_ACCOUNT_ID")

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if request.seed is not None:
            payload["seed"] = request.seed
        account_path = quote(self.account_id.get_secret_value(), safe="")
        model_path = quote(request.model_id, safe="@/")
        started = perf_counter()
        response = self.transport.post(
            f"{CLOUDFLARE_API_ROOT}/{account_path}/ai/run/{model_path}",
            {"Authorization": f"Bearer {self.credential.get_secret_value()}"},
            payload,
        )
        latency_ms = (perf_counter() - started) * 1000
        envelope = response.document
        if envelope.get("success") is False:
            raise ClassifiedFailure(
                "configuration/configuration_drift",
                "Cloudflare returned an unsuccessful API envelope",
                http_status=response.status,
            )
        result = as_mapping(envelope.get("result"), "Cloudflare result is missing or invalid")
        text = self._result_text(result, http_status=response.status)
        usage_value = result.get("usage")
        usage = as_mapping(usage_value, "Cloudflare usage is invalid") if usage_value is not None else {}
        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        return ProviderResponse(
            provider=self.name,
            requested_model_id=request.model_id,
            reported_model_id=optional_string(result.get("model")),
            text=text,
            usage=TokenUsage(
                optional_token(input_tokens, "Cloudflare input token count is invalid"),
                optional_token(output_tokens, "Cloudflare output token count is invalid"),
                "cloudflare_reported_usage_or_null",
            ),
            latency_ms=latency_ms,
            response_id=optional_string(result.get("id")) or optional_string(envelope.get("result_info")),
            http_status=response.status,
        )

    @staticmethod
    def _result_text(result: dict[str, Any], *, http_status: int) -> str:
        direct = result.get("response")
        if isinstance(direct, str):
            return direct
        choices_value = result.get("choices")
        if choices_value is not None:
            choices = as_sequence(choices_value, "Cloudflare choices is invalid")
            if choices:
                choice = as_mapping(choices[0], "first Cloudflare choice is not an object")
                message = as_mapping(choice.get("message"), "Cloudflare choice message is missing")
                content = message.get("content")
                finish_reason = choice.get("finish_reason")
                if content is None and finish_reason in {
                    "length",
                    "max_output_tokens",
                    "max_tokens",
                }:
                    raise ClassifiedFailure(
                        "configuration/output_cap_truncation",
                        "Cloudflare exhausted the output cap before emitting final content",
                        http_status=http_status,
                    )
                return chat_content_text(content)
        raise schema_failure("Cloudflare result contains no response text")

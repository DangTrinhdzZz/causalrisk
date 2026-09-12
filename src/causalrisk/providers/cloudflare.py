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
        try:
            response = self.transport.post(
                f"{CLOUDFLARE_API_ROOT}/{account_path}/ai/run/{model_path}",
                {"Authorization": f"Bearer {self.credential.get_secret_value()}"},
                payload,
            )
        except ClassifiedFailure as failure:
            failure.latency_ms = (perf_counter() - started) * 1000
            raise
        latency_ms = (perf_counter() - started) * 1000
        envelope = response.document
        if envelope.get("success") is False:
            raise ClassifiedFailure(
                "configuration/configuration_drift",
                "Cloudflare returned an unsuccessful API envelope",
                http_status=response.status,
            )
        result = as_mapping(envelope.get("result"), "Cloudflare result is missing or invalid")
        usage_value = result.get("usage")
        usage = as_mapping(usage_value, "Cloudflare usage is invalid") if usage_value is not None else {}
        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        prompt_details_value = usage.get("prompt_tokens_details")
        prompt_details = (
            as_mapping(prompt_details_value, "Cloudflare prompt_tokens_details is invalid")
            if prompt_details_value is not None
            else {}
        )
        completion_details_value = usage.get("completion_tokens_details")
        completion_details = (
            as_mapping(completion_details_value, "Cloudflare completion_tokens_details is invalid")
            if completion_details_value is not None
            else {}
        )
        token_usage = TokenUsage(
            optional_token(input_tokens, "Cloudflare input token count is invalid"),
            optional_token(output_tokens, "Cloudflare output token count is invalid"),
            "cloudflare_reported_usage_or_null",
            reasoning_tokens=optional_token(
                completion_details.get("reasoning_tokens"), "Cloudflare reasoning_tokens is invalid"
            ),
            cached_input_tokens=optional_token(
                prompt_details.get("cached_tokens"), "Cloudflare cached_tokens is invalid"
            ),
        )
        finish_reason = self._finish_reason(result)
        response_id = optional_string(result.get("id")) or optional_string(envelope.get("result_info"))
        if finish_reason in {"length", "max_output_tokens", "max_tokens"}:
            raise ClassifiedFailure(
                "configuration/output_cap_truncation",
                "Cloudflare exhausted the output cap",
                http_status=response.status,
                finish_reason=finish_reason,
                latency_ms=latency_ms,
                response_id=response_id,
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens,
                reasoning_tokens=token_usage.reasoning_tokens,
                cached_input_tokens=token_usage.cached_input_tokens,
                total_tokens=token_usage.total_tokens,
                token_accounting_method=token_usage.accounting_method,
                safe_response_headers=response.headers,
            )
        text = self._result_text(result)
        return ProviderResponse(
            provider=self.name,
            requested_model_id=request.model_id,
            reported_model_id=optional_string(result.get("model")),
            text=text,
            usage=token_usage,
            latency_ms=latency_ms,
            response_id=response_id,
            http_status=response.status,
            finish_reason=finish_reason,
            safe_response_headers=response.headers,
        )

    @staticmethod
    def _finish_reason(result: dict[str, Any]) -> str | None:
        direct = optional_string(result.get("finish_reason"))
        if direct is not None:
            return direct
        choices_value = result.get("choices")
        if choices_value is None:
            return None
        choices = as_sequence(choices_value, "Cloudflare choices is invalid")
        if not choices:
            return None
        choice = as_mapping(choices[0], "first Cloudflare choice is not an object")
        return optional_string(choice.get("finish_reason"))

    @staticmethod
    def _result_text(result: dict[str, Any]) -> str:
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
                return chat_content_text(content)
        raise schema_failure("Cloudflare result contains no response text")

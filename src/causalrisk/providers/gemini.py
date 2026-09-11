"""Google Gemini generateContent adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from urllib.parse import quote

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

GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass(slots=True)
class GeminiGenerateContentAdapter:
    credential: SecretValue
    transport: JsonHttpTransport = field(default_factory=StdlibJsonHttpTransport)
    name: str = field(init=False, default="gemini")
    credential_environment_variable: str = field(init=False, default="GEMINI_API_KEY")

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        generation_config: dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_output_tokens,
        }
        if request.seed is not None:
            generation_config["seed"] = request.seed
        payload = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": generation_config,
        }
        model_path = quote(request.model_id.removeprefix("models/"), safe="")
        started = perf_counter()
        response = self.transport.post(
            f"{GEMINI_API_ROOT}/{model_path}:generateContent",
            {"x-goog-api-key": self.credential.get_secret_value()},
            payload,
        )
        latency_ms = (perf_counter() - started) * 1000
        document = response.document
        candidates_value = document.get("candidates")
        if candidates_value is None:
            prompt_feedback = document.get("promptFeedback")
            if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
                raise ClassifiedFailure(
                    "response/safety_refusal",
                    "Gemini blocked the prompt for safety",
                    http_status=response.status,
                )
            raise schema_failure("Gemini candidates is missing")
        candidates = as_sequence(candidates_value, "Gemini candidates is invalid")
        if not candidates:
            raise schema_failure("Gemini candidates is empty")
        candidate = as_mapping(candidates[0], "first Gemini candidate is not an object")
        finish_reason = optional_string(candidate.get("finishReason"))
        if finish_reason == "MAX_TOKENS":
            raise ClassifiedFailure(
                "configuration/output_cap_truncation",
                "Gemini stopped at the configured output cap",
                http_status=response.status,
            )
        if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise ClassifiedFailure(
                "response/safety_refusal",
                "Gemini blocked the response for safety",
                http_status=response.status,
            )
        content = as_mapping(candidate.get("content"), "Gemini candidate content is missing")
        parts = as_sequence(content.get("parts"), "Gemini content parts is missing or invalid")
        texts: list[str] = []
        for part_value in parts:
            part = as_mapping(part_value, "Gemini content part is not an object")
            if isinstance(part.get("text"), str):
                texts.append(part["text"])
        if not texts:
            raise schema_failure("Gemini candidate contains no text")
        usage_value = document.get("usageMetadata")
        usage = as_mapping(usage_value, "Gemini usageMetadata is invalid") if usage_value is not None else {}
        candidate_tokens = optional_token(usage.get("candidatesTokenCount"), "candidatesTokenCount is invalid")
        reasoning_tokens = optional_token(usage.get("thoughtsTokenCount"), "thoughtsTokenCount is invalid")
        output_tokens = (
            candidate_tokens + (reasoning_tokens or 0) if candidate_tokens is not None else None
        )
        return ProviderResponse(
            provider=self.name,
            requested_model_id=request.model_id,
            reported_model_id=optional_string(document.get("modelVersion")),
            text="\n".join(texts),
            usage=TokenUsage(
                optional_token(usage.get("promptTokenCount"), "promptTokenCount is invalid"),
                output_tokens,
                "gemini_reported_usage_metadata",
                reasoning_tokens=reasoning_tokens,
                cached_input_tokens=optional_token(
                    usage.get("cachedContentTokenCount"), "cachedContentTokenCount is invalid"
                ),
            ),
            latency_ms=latency_ms,
            response_id=optional_string(document.get("responseId")),
            http_status=response.status,
        )

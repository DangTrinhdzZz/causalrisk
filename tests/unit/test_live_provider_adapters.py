from dataclasses import dataclass, field

import pytest

from causalrisk.credentials import SecretValue
from causalrisk.providers.candidates import PROVIDER_CANDIDATES
from causalrisk.providers.cloudflare import CloudflareWorkersAIAdapter
from causalrisk.providers.gemini import GeminiGenerateContentAdapter
from causalrisk.providers.http import JsonHttpResponse, classify_http_status, extract_provider_error_metadata
from causalrisk.providers.openai import OpenAIResponsesAdapter
from causalrisk.providers.openai_compatible import OpenAICompatibleChatAdapter
from causalrisk.retry import ClassifiedFailure


@dataclass
class FakeTransport:
    document: dict
    status: int = 200
    calls: list = field(default_factory=list)

    def post(self, url, headers, payload):
        self.calls.append((url, headers, payload))
        return JsonHttpResponse(self.status, {}, self.document)


def request(model="model-v1", seed=None):
    from causalrisk.providers import ProviderRequest

    return ProviderRequest("Return YES.", model, 0.0, 8, seed)


def test_openai_responses_adapter_extracts_text_usage_and_never_stores_response():
    transport = FakeTransport(
        {
            "id": "resp_1",
            "model": "gpt-test",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "YES"}],
                }
            ],
            "usage": {"input_tokens": 7, "output_tokens": 1},
        }
    )
    response = OpenAIResponsesAdapter(SecretValue("fake-openai"), transport).complete(request("gpt-test"))
    assert response.text == "YES"
    assert response.usage.total_tokens == 8
    assert response.response_id == "resp_1"
    _, headers, payload = transport.calls[0]
    assert headers["Authorization"] == "Bearer fake-openai"
    assert payload["store"] is False
    assert payload["max_output_tokens"] == 8


def test_openai_responses_adapter_classifies_output_cap_and_refusal():
    truncated = FakeTransport(
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
        }
    )
    with pytest.raises(ClassifiedFailure) as cap_error:
        OpenAIResponsesAdapter(SecretValue("fake"), truncated).complete(request())
    assert cap_error.value.failure_code == "configuration/output_cap_truncation"

    refused = FakeTransport(
        {
            "status": "completed",
            "output": [{"content": [{"type": "refusal", "refusal": "cannot help"}]}],
        }
    )
    with pytest.raises(ClassifiedFailure) as refusal_error:
        OpenAIResponsesAdapter(SecretValue("fake"), refused).complete(request())
    assert refusal_error.value.failure_code == "response/safety_refusal"


def test_openai_compatible_adapter_uses_declared_provider_fields():
    transport = FakeTransport(
        {
            "id": "chat_1",
            "model": "served-model",
            "choices": [{"message": {"content": "YES"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        }
    )
    adapter = OpenAICompatibleChatAdapter(
        "groq",
        "GROQ_API_KEY",
        SecretValue("fake-groq"),
        "https://example.invalid/chat",
        max_tokens_field="max_completion_tokens",
        seed_field="seed",
        transport=transport,
    )
    response = adapter.complete(request("requested-model", seed=17))
    assert response.provider == "groq"
    assert response.reported_model_id == "served-model"
    assert response.usage.total_tokens == 6
    _, _, payload = transport.calls[0]
    assert payload["max_completion_tokens"] == 8
    assert payload["seed"] == 17
    assert payload["stream"] is False


def test_gemini_adapter_extracts_generate_content_shape():
    transport = FakeTransport(
        {
            "responseId": "gem_1",
            "modelVersion": "gemini-test-001",
            "candidates": [
                {
                    "content": {"parts": [{"text": "YES"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 1},
        }
    )
    response = GeminiGenerateContentAdapter(SecretValue("fake-gemini"), transport).complete(request("gemini-test"))
    assert response.text == "YES"
    assert response.usage.total_tokens == 5
    url, headers, payload = transport.calls[0]
    assert url.endswith("/gemini-test:generateContent")
    assert headers["x-goog-api-key"] == "fake-gemini"
    assert payload["generationConfig"]["maxOutputTokens"] == 8


def test_cloudflare_adapter_uses_account_path_and_extracts_usage():
    transport = FakeTransport(
        {
            "success": True,
            "result": {
                "response": "YES",
                "usage": {"prompt_tokens": 6, "completion_tokens": 1},
            },
        }
    )
    response = CloudflareWorkersAIAdapter(
        SecretValue("fake-token"),
        SecretValue("fake-account"),
        transport,
    ).complete(request("@cf/qwen/test"))
    assert response.text == "YES"
    assert response.usage.total_tokens == 7
    url, headers, _ = transport.calls[0]
    assert "/fake-account/ai/run/@cf/qwen/test" in url
    assert headers["Authorization"] == "Bearer fake-token"


@pytest.mark.parametrize(
    ("status", "failure_code"),
    [
        (400, "configuration/malformed_request"),
        (401, "configuration/authentication"),
        (404, "configuration/nonexistent_model"),
        (429, "provider/http_429"),
        (500, "provider/http_5xx"),
    ],
)
def test_http_statuses_map_to_frozen_taxonomy(status, failure_code):
    failure = classify_http_status(status, "2.5")
    assert failure.failure_code == failure_code
    assert failure.http_status == status
    if status == 429:
        assert failure.retry_after_seconds == 2.5


def test_provider_error_metadata_keeps_only_allowlisted_non_message_fields():
    raw = (
        b'{"error":{"message":"do not retain this body",'
        b'"type":"invalid_request_error","param":"temperature","code":"unsupported_value"}}'
    )
    assert extract_provider_error_metadata(raw) == (
        "unsupported_value",
        "invalid_request_error",
        "temperature",
    )
    failure = classify_http_status(
        400,
        provider_error_code="unsupported_value",
        provider_error_type="invalid_request_error",
        provider_error_param="temperature",
    )
    assert failure.failure_code == "configuration/malformed_request"
    assert "do not retain" not in str(failure)


def test_provider_error_metadata_rejects_secret_like_or_unstructured_values():
    raw = b'{"error":{"code":"sk-this-must-not-be-retained","type":"bad value with spaces"}}'
    assert extract_provider_error_metadata(raw) == (None, None, None)


def test_model_not_found_and_quota_codes_override_ambiguous_http_statuses():
    missing = classify_http_status(400, provider_error_code="model_not_found")
    quota = classify_http_status(429, provider_error_code="insufficient_quota")
    assert missing.failure_code == "configuration/nonexistent_model"
    assert quota.failure_code == "configuration/quota_exhaustion"


def test_primary_council_candidate_families_are_distinct_and_nvidia_is_reserve():
    primary = [candidate for candidate in PROVIDER_CANDIDATES.values() if candidate.primary]
    assert len(primary) == 5
    assert len({candidate.model_family for candidate in primary}) == 5
    assert PROVIDER_CANDIDATES["openai"].intended_role == "adjudicator"
    assert PROVIDER_CANDIDATES["nvidia_nim"].primary is False

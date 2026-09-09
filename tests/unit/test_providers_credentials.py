from dataclasses import dataclass

import pytest

from causalrisk.credentials import MissingCredentialError, load_credential
from causalrisk.providers import ProviderRegistry, ProviderRequest, ProviderResponse
from causalrisk.usage import TokenUsage


@dataclass
class FakeAdapter:
    name: str = "fake"
    credential_environment_variable: str = "FAKE_API_KEY"

    def complete(self, request):
        return ProviderResponse(
            provider=self.name,
            requested_model_id=request.model_id,
            reported_model_id=request.model_id,
            text="YES",
            usage=TokenUsage(1, 1, "synthetic"),
            latency_ms=1,
        )


def test_registry_requires_explicit_unique_provider():
    registry = ProviderRegistry()
    registry.register(FakeAdapter())
    assert registry.get("fake").name == "fake"
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeAdapter())


def test_provider_request_rejects_empty_or_invalid_values():
    with pytest.raises(ValueError):
        ProviderRequest("", "model", 0.0, 8)
    with pytest.raises(ValueError):
        ProviderRequest("prompt", "model", 0.0, 0)


def test_credential_repr_and_str_are_redacted(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "top-secret-value")
    secret = load_credential("FAKE_API_KEY")
    assert "top-secret-value" not in repr(secret)
    assert str(secret) == "[REDACTED]"
    assert secret.get_secret_value() == "top-secret-value"


def test_missing_credential_fails_closed(monkeypatch):
    monkeypatch.delenv("FAKE_API_KEY", raising=False)
    with pytest.raises(MissingCredentialError, match="FAKE_API_KEY"):
        load_credential("FAKE_API_KEY")

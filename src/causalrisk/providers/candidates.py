"""Pre-execution provider candidates; none are runtime verified by this module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCandidate:
    provider: str
    credential_environment_variable: str
    factory_specification: str
    model_id: str
    model_family: str
    intended_role: str
    primary: bool


PROVIDER_CANDIDATES: dict[str, ProviderCandidate] = {
    "groq": ProviderCandidate(
        "groq",
        "GROQ_API_KEY",
        "causalrisk.providers.factories:create_groq_adapter",
        "openai/gpt-oss-120b",
        "gpt-oss",
        "analyst",
        True,
    ),
    "mistral": ProviderCandidate(
        "mistral",
        "MISTRAL_API_KEY",
        "causalrisk.providers.factories:create_mistral_adapter",
        "mistral-large-2512",
        "mistral-large",
        "critic",
        True,
    ),
    "gemini": ProviderCandidate(
        "gemini",
        "GEMINI_API_KEY",
        "causalrisk.providers.factories:create_gemini_adapter",
        "gemini-3.8-flash",
        "gemini-3.8",
        "semantic_query_critic",
        True,
    ),
    "cloudflare_workers_ai": ProviderCandidate(
        "cloudflare_workers_ai",
        "CLOUDFLARE_API_TOKEN",
        "causalrisk.providers.factories:create_cloudflare_adapter",
        "@cf/qwen/qwen3-30b-a3b-fp8",
        "qwen3",
        "formal_numerical_critic",
        True,
    ),
    "openai": ProviderCandidate(
        "openai",
        "OPENAI_API_KEY",
        "causalrisk.providers.factories:create_openai_adapter",
        "gpt-5.6-terra",
        "gpt-5.6",
        "adjudicator",
        True,
    ),
    "nvidia_nim": ProviderCandidate(
        "nvidia_nim",
        "NVIDIA_API_KEY",
        "causalrisk.providers.factories:create_nvidia_adapter",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "nemotron-3.5",
        "reserve",
        False,
    ),
}

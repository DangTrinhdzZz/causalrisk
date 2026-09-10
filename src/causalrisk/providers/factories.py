"""Explicit live-adapter factories used by the authorized smoke CLI."""

from __future__ import annotations

from causalrisk.credentials import SecretValue, load_credential
from causalrisk.providers.cloudflare import CloudflareWorkersAIAdapter
from causalrisk.providers.gemini import GeminiGenerateContentAdapter
from causalrisk.providers.openai import OpenAIResponsesAdapter
from causalrisk.providers.openai_compatible import OpenAICompatibleChatAdapter


def create_groq_adapter(credential: SecretValue) -> OpenAICompatibleChatAdapter:
    return OpenAICompatibleChatAdapter(
        name="groq",
        credential_environment_variable="GROQ_API_KEY",
        credential=credential,
        endpoint="https://api.groq.com/openai/v1/chat/completions",
        max_tokens_field="max_completion_tokens",
        seed_field="seed",
    )


def create_mistral_adapter(credential: SecretValue) -> OpenAICompatibleChatAdapter:
    return OpenAICompatibleChatAdapter(
        name="mistral",
        credential_environment_variable="MISTRAL_API_KEY",
        credential=credential,
        endpoint="https://api.mistral.ai/v1/chat/completions",
        max_tokens_field="max_tokens",
        seed_field="random_seed",
    )


def create_nvidia_adapter(credential: SecretValue) -> OpenAICompatibleChatAdapter:
    return OpenAICompatibleChatAdapter(
        name="nvidia_nim",
        credential_environment_variable="NVIDIA_API_KEY",
        credential=credential,
        endpoint="https://integrate.api.nvidia.com/v1/chat/completions",
        max_tokens_field="max_tokens",
        seed_field="seed",
    )


def create_gemini_adapter(credential: SecretValue) -> GeminiGenerateContentAdapter:
    return GeminiGenerateContentAdapter(credential)


def create_cloudflare_adapter(credential: SecretValue) -> CloudflareWorkersAIAdapter:
    return CloudflareWorkersAIAdapter(credential, load_credential("CLOUDFLARE_ACCOUNT_ID"))


def create_openai_adapter(credential: SecretValue) -> OpenAIResponsesAdapter:
    return OpenAIResponsesAdapter(credential)

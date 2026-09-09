"""Explicit provider registry that prevents silent adapter substitution."""

from __future__ import annotations

from causalrisk.providers.base import ProviderAdapter


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        if not isinstance(adapter, ProviderAdapter):
            raise TypeError("adapter does not implement ProviderAdapter")
        if not adapter.name.strip():
            raise ValueError("adapter name must be non-empty")
        if adapter.name in self._adapters:
            raise ValueError(f"provider adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, provider: str) -> ProviderAdapter:
        try:
            return self._adapters[provider]
        except KeyError as error:
            raise KeyError(f"provider adapter is not registered: {provider}") from error

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

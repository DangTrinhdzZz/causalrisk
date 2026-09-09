"""Fail-closed environment credential access with redacted representation."""

from __future__ import annotations

import os
from dataclasses import dataclass


class MissingCredentialError(RuntimeError):
    """Raised without disclosing any credential value."""


@dataclass(frozen=True, slots=True)
class SecretValue:
    _value: str

    def __repr__(self) -> str:
        return "SecretValue('[REDACTED]')"

    def __str__(self) -> str:
        return "[REDACTED]"

    def get_secret_value(self) -> str:
        """Reveal only at the transport boundary that needs authentication."""

        return self._value


def load_credential(environment_variable: str) -> SecretValue:
    if not environment_variable or not environment_variable.replace("_", "").isalnum():
        raise ValueError("invalid credential environment-variable name")
    value = os.environ.get(environment_variable)
    if value is None or not value.strip():
        raise MissingCredentialError(f"required credential is absent: {environment_variable}")
    return SecretValue(value)

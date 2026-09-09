#!/usr/bin/env python3
"""Run one explicitly authorized, non-benchmark provider connectivity test."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable
from typing import Any

from causalrisk.credentials import SecretValue, load_credential
from causalrisk.parsing import parse_yesno
from causalrisk.providers import ProviderAdapter, ProviderRequest
from causalrisk.retry import ClassifiedFailure, RetryEvent, call_with_retries

SMOKE_PROMPT = (
    "This is a non-benchmark transport test. Use no external tools. "
    "Is the arithmetic statement 2 + 2 = 4 true? Reply with exactly one line: YES or NO."
)


def _factory(specification: str) -> Callable[[SecretValue], ProviderAdapter]:
    try:
        module_name, function_name = specification.split(":", 1)
        value: Any = getattr(importlib.import_module(module_name), function_name)
    except (ValueError, ImportError, AttributeError) as error:
        raise ValueError("adapter factory must use importable module:function syntax") from error
    if not callable(value):
        raise TypeError("adapter factory is not callable")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-factory", required=True, help="verified adapter factory as module:function")
    parser.add_argument("--credential-env", required=True, help="environment variable containing the provider key")
    parser.add_argument("--model", required=True, help="exact model ID being verified")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=8)
    parser.add_argument(
        "--authorize-live-call",
        action="store_true",
        help="required acknowledgement that this command makes one non-benchmark live call plus eligible retries",
    )
    args = parser.parse_args()
    if not args.authorize_live_call:
        raise SystemExit("Blocked: add --authorize-live-call only when the intended smoke call is approved.")

    credential = load_credential(args.credential_env)
    adapter = _factory(args.adapter_factory)(credential)
    request = ProviderRequest(
        prompt=SMOKE_PROMPT,
        model_id=args.model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )
    retry_events: list[RetryEvent] = []
    def complete_attempt(_attempt_index: int):
        result = adapter.complete(request)
        if not result.text.strip():
            raise ClassifiedFailure("response/empty_content", "provider returned empty content")
        return result

    response = call_with_retries(complete_attempt, on_retry_event=retry_events.append)
    parsed = parse_yesno(response.text)
    print(
        "Smoke response received; "
        f"provider={response.provider}, model={response.reported_model_id or response.requested_model_id}, "
        f"parsed={parsed.answer}, latency_ms={response.latency_ms:.1f}, retries={len(retry_events)}, "
        f"input_tokens={response.usage.input_tokens}, output_tokens={response.usage.output_tokens}."
    )
    if parsed.answer == "INVALID":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run one explicitly authorized, non-benchmark provider connectivity test."""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from causalrisk.credentials import MissingCredentialError, SecretValue, load_credential
from causalrisk.parsing import parse_yesno
from causalrisk.providers import ProviderAdapter, ProviderRequest, ProviderResponse
from causalrisk.providers.candidates import PROVIDER_CANDIDATES
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
    parser.add_argument("--provider", choices=sorted(PROVIDER_CANDIDATES), help="one declared provider candidate")
    parser.add_argument("--list-candidates", action="store_true", help="show candidates without loading credentials")
    parser.add_argument("--adapter-factory", help="advanced override using importable module:function syntax")
    parser.add_argument("--credential-env", help="environment variable containing the provider key")
    parser.add_argument("--model", help="exact model ID being verified; defaults to the selected candidate")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=8)
    parser.add_argument("--write-report", action="store_true", help="write a redacted report under artifacts/smoke")
    parser.add_argument(
        "--authorize-live-call",
        action="store_true",
        help="required acknowledgement that this command makes one non-benchmark live call plus eligible retries",
    )
    args = parser.parse_args()

    if args.list_candidates:
        if args.provider or args.adapter_factory or args.authorize_live_call:
            parser.error("--list-candidates cannot be combined with a live-call option")
        for candidate in PROVIDER_CANDIDATES.values():
            status = "primary" if candidate.primary else "reserve"
            print(
                f"{candidate.provider}: model={candidate.model_id}, family={candidate.model_family}, "
                f"role={candidate.intended_role}, status={status}"
            )
        return

    if args.provider and args.adapter_factory:
        parser.error("choose either --provider or --adapter-factory, not both")
    if args.provider:
        candidate = PROVIDER_CANDIDATES[args.provider]
        factory_specification = candidate.factory_specification
        credential_environment = candidate.credential_environment_variable
        model_id = args.model or candidate.model_id
    else:
        if not args.adapter_factory or not args.credential_env or not args.model:
            parser.error("use --provider, or provide --adapter-factory, --credential-env, and --model")
        factory_specification = args.adapter_factory
        credential_environment = args.credential_env
        model_id = args.model

    if not args.authorize_live_call:
        raise SystemExit("Blocked: add --authorize-live-call only when the intended smoke call is approved.")

    try:
        credential = load_credential(credential_environment)
        adapter = _factory(factory_specification)(credential)
    except MissingCredentialError as error:
        raise SystemExit(str(error)) from None
    request = ProviderRequest(
        prompt=SMOKE_PROMPT,
        model_id=model_id,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )
    retry_events: list[RetryEvent] = []

    def complete_attempt(_attempt_index: int):
        result = adapter.complete(request)
        if not result.text.strip():
            raise ClassifiedFailure("response/empty_content", "provider returned empty content")
        return result

    try:
        response = call_with_retries(complete_attempt, on_retry_event=retry_events.append)
    except ClassifiedFailure as failure:
        print(
            "Smoke failed; "
            f"provider={adapter.name}, model={model_id}, failure_code={failure.failure_code}, "
            f"http_status={failure.http_status}, failed_attempts={len(retry_events)}."
        )
        if args.write_report:
            report_path = _write_failure_report(adapter.name, model_id, failure, retry_events)
            print(f"Redacted smoke report written to {_display_path(report_path)}.")
        raise SystemExit(1) from None
    parsed = parse_yesno(response.text)
    print(
        "Smoke response received; "
        f"provider={response.provider}, model={response.reported_model_id or response.requested_model_id}, "
        f"parsed={parsed.answer}, latency_ms={response.latency_ms:.1f}, retries={len(retry_events)}, "
        f"input_tokens={response.usage.input_tokens}, output_tokens={response.usage.output_tokens}."
    )
    if args.write_report:
        report_path = _write_success_report(response, parsed.answer, retry_events)
        print(f"Redacted smoke report written to {_display_path(report_path)}.")
    if parsed.answer == "INVALID":
        raise SystemExit(1)


def _report_path(provider: str, timestamp: datetime) -> Path:
    root = Path(__file__).resolve().parents[1]
    report_directory = root / "artifacts" / "smoke"
    report_directory.mkdir(parents=True, exist_ok=True)
    safe_provider = provider.replace("/", "_")
    return report_directory / f"{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}-{safe_provider}.json"


def _retry_records(retry_events: list[RetryEvent]) -> list[dict[str, Any]]:
    return [
        {
            "attempt_index": event.attempt_index,
            "failure_code": event.failure_code,
            "http_status": event.http_status,
            "retry_eligible": event.decision.retry_eligible,
            "backoff_seconds": event.decision.backoff_seconds,
            "resolution_action": event.decision.resolution_action,
        }
        for event in retry_events
    ]


def _write_success_report(
    response: ProviderResponse,
    parsed_answer: str,
    retry_events: list[RetryEvent],
) -> Path:
    timestamp = datetime.now(UTC)
    path = _report_path(response.provider, timestamp)
    report = {
        "schema_version": 1,
        "smoke_kind": "synthetic_non_benchmark",
        "status": "success" if parsed_answer != "INVALID" else "invalid_output",
        "timestamp_utc": timestamp.isoformat(),
        "provider": response.provider,
        "requested_model_id": response.requested_model_id,
        "reported_model_id": response.reported_model_id,
        "parsed_answer": parsed_answer,
        "latency_ms": response.latency_ms,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "accounting_method": response.usage.accounting_method,
        "http_status": response.http_status,
        "response_id": response.response_id,
        "retry_events": _retry_records(retry_events),
        "contains_raw_output": False,
        "runtime_verified": False,
        "note": "A successful transport smoke does not by itself freeze or enable a benchmark config.",
    }
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _write_failure_report(
    provider: str,
    requested_model_id: str,
    failure: ClassifiedFailure,
    retry_events: list[RetryEvent],
) -> Path:
    timestamp = datetime.now(UTC)
    path = _report_path(provider, timestamp)
    report = {
        "schema_version": 1,
        "smoke_kind": "synthetic_non_benchmark",
        "status": "failure",
        "timestamp_utc": timestamp.isoformat(),
        "provider": provider,
        "requested_model_id": requested_model_id,
        "failure_code": failure.failure_code,
        "http_status": failure.http_status,
        "retry_events": _retry_records(retry_events),
        "contains_raw_output": False,
        "runtime_verified": False,
        "note": "Failure details are intentionally redacted; inspect the provider console separately if needed.",
    }
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _display_path(path: Path) -> Path:
    return path.relative_to(Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    main()

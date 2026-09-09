import pytest

from causalrisk.retry import ClassifiedFailure, RetryExhausted, call_with_retries, decide_retry


def test_eligible_failures_use_fixed_one_two_four_backoff():
    attempts = []
    events = []
    sleeps = []

    def operation(attempt_index):
        attempts.append(attempt_index)
        if attempt_index < 3:
            raise ClassifiedFailure("transport/timeout", "timed out")
        return "ok"

    result = call_with_retries(operation, on_retry_event=events.append, sleep=sleeps.append)
    assert result == "ok"
    assert attempts == [0, 1, 2, 3]
    assert sleeps == [1.0, 2.0, 4.0]
    assert all(event.decision.retry_eligible for event in events)


def test_retry_after_is_respected_for_http_429():
    failure = ClassifiedFailure("provider/http_429", "rate limited", retry_after_seconds=2.5)
    assert decide_retry(failure, 0).backoff_seconds == 2.5


def test_invalid_label_is_not_retried():
    calls = []

    def operation(attempt_index):
        calls.append(attempt_index)
        raise ClassifiedFailure("invalid_label", "bad label")

    with pytest.raises(ClassifiedFailure, match="bad label"):
        call_with_retries(operation, on_retry_event=lambda _event: None, sleep=lambda _seconds: None)
    assert calls == [0]


def test_four_eligible_failures_exhaust_budget():
    with pytest.raises(RetryExhausted):
        call_with_retries(
            lambda _attempt: (_ for _ in ()).throw(ClassifiedFailure("response/empty_content", "empty")),
            on_retry_event=lambda _event: None,
            sleep=lambda _seconds: None,
        )

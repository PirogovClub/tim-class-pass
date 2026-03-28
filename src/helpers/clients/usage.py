from __future__ import annotations

from collections import defaultdict
from typing import Any
import uuid


def _get_value(source: Any, *names: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        for name in names:
            if name in source and source[name] is not None:
                return source[name]
        return None
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_usage_record(
    *,
    provider: str,
    model: str,
    usage: Any = None,
    stage: str | None = None,
    operation: str | None = None,
    attempt: int = 1,
    status: str = "succeeded",
    request_id: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt_tokens = _as_int(
        _get_value(
            usage,
            "prompt_token_count",
            "input_token_count",
            "prompt_tokens",
            "input_tokens",
        )
    )
    output_tokens = _as_int(
        _get_value(
            usage,
            "candidates_token_count",
            "output_token_count",
            "completion_tokens",
            "output_tokens",
        )
    )
    total_tokens = _as_int(
        _get_value(
            usage,
            "total_token_count",
            "total_tokens",
        )
    )
    if total_tokens is None and prompt_tokens is not None and output_tokens is not None:
        total_tokens = prompt_tokens + output_tokens

    record = {
        "request_id": request_id or str(uuid.uuid4()),
        "provider": provider,
        "model": model,
        "stage": stage,
        "operation": operation,
        "attempt": max(int(attempt), 1),
        "status": status,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "usage_available": any(value is not None for value in (prompt_tokens, output_tokens, total_tokens)),
        "error": error,
    }
    if extra:
        record.update(extra)
    return record


def summarize_usage_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "request_count": 0,
        "succeeded": 0,
        "failed": 0,
        "usage_available_count": 0,
        "prompt_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    by_provider: dict[str, dict[str, Any]] = defaultdict(dict)
    by_model: dict[str, dict[str, Any]] = defaultdict(dict)
    by_stage: dict[str, dict[str, Any]] = defaultdict(dict)
    by_status: dict[str, dict[str, Any]] = defaultdict(dict)

    def _accumulate(bucket: dict[str, Any], record: dict[str, Any]) -> None:
        bucket["request_count"] = int(bucket.get("request_count", 0)) + 1
        bucket["succeeded"] = int(bucket.get("succeeded", 0)) + int(record.get("status") == "succeeded")
        bucket["failed"] = int(bucket.get("failed", 0)) + int(record.get("status") != "succeeded")
        bucket["usage_available_count"] = int(bucket.get("usage_available_count", 0)) + int(
            bool(record.get("usage_available"))
        )
        bucket["prompt_tokens"] = int(bucket.get("prompt_tokens", 0)) + int(record.get("prompt_tokens") or 0)
        bucket["output_tokens"] = int(bucket.get("output_tokens", 0)) + int(record.get("output_tokens") or 0)
        bucket["total_tokens"] = int(bucket.get("total_tokens", 0)) + int(record.get("total_tokens") or 0)

    for record in records:
        totals["request_count"] += 1
        totals["succeeded"] += int(record.get("status") == "succeeded")
        totals["failed"] += int(record.get("status") != "succeeded")
        totals["usage_available_count"] += int(bool(record.get("usage_available")))
        totals["prompt_tokens"] += int(record.get("prompt_tokens") or 0)
        totals["output_tokens"] += int(record.get("output_tokens") or 0)
        totals["total_tokens"] += int(record.get("total_tokens") or 0)

        _accumulate(by_provider[record.get("provider") or "unknown"], record)
        _accumulate(by_model[record.get("model") or "unknown"], record)
        _accumulate(by_stage[record.get("stage") or "unknown"], record)
        _accumulate(by_status[record.get("status") or "unknown"], record)

    return {
        "totals": totals,
        "by_provider": dict(sorted(by_provider.items())),
        "by_model": dict(sorted(by_model.items())),
        "by_stage": dict(sorted(by_stage.items())),
        "by_status": dict(sorted(by_status.items())),
    }

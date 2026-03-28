"""Validate and normalize candidate market windows for Step 6 label generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_BAR_KEYS = frozenset({"open", "high", "low", "close", "volume"})
ALLOWED_TIMEFRAMES = frozenset({"1m", "5m", "15m", "1h", "4h", "1d"})


@dataclass
class WindowValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    point_in_time_safe: bool = True


def _as_float(x: Any, path: str) -> tuple[float | None, str | None]:
    if x is None:
        return None, f"{path} is required"
    try:
        return float(x), None
    except (TypeError, ValueError):
        return None, f"{path} must be numeric"


def validate_market_window(
    window: dict[str, Any],
    *,
    max_forward_bars: int,
    min_context_bars_inclusive_anchor: int,
) -> WindowValidationResult:
    """Structural + PIT-boundary checks. Does not run label logic."""
    errs: list[str] = []

    cid = window.get("candidate_id")
    if not isinstance(cid, str) or not cid.strip():
        errs.append("candidate_id must be a non-empty string")

    L, e = _as_float(window.get("reference_level"), "reference_level")
    if e:
        errs.append(e)

    anchor_ts = window.get("anchor_timestamp")
    if not isinstance(anchor_ts, str) or not anchor_ts.strip():
        errs.append("anchor_timestamp must be a non-empty string")

    tf = window.get("timeframe")
    if not isinstance(tf, str) or tf not in ALLOWED_TIMEFRAMES:
        errs.append(f"timeframe must be one of {sorted(ALLOWED_TIMEFRAMES)}")

    approach = window.get("approach_direction")
    if approach is not None and approach not in ("from_below", "from_above", "unknown"):
        errs.append("approach_direction must be from_below|from_above|unknown")

    idx = window.get("anchor_bar_index")
    if not isinstance(idx, int) or idx < 0:
        errs.append("anchor_bar_index must be a non-negative int")

    bba = window.get("bars_before_anchor")
    if bba is not None:
        if not isinstance(bba, int) or bba < 0:
            errs.append("bars_before_anchor must be a non-negative int when present")
        elif isinstance(idx, int) and bba != idx:
            errs.append(
                f"bars_before_anchor ({bba}) must equal anchor_bar_index ({idx}) "
                "(count of bars strictly before the anchor bar)"
            )

    bars = window.get("bars")
    if not isinstance(bars, list) or len(bars) == 0:
        errs.append("bars must be a non-empty list")
        return WindowValidationResult(ok=False, errors=errs, point_in_time_safe=False)

    if isinstance(idx, int) and idx >= len(bars):
        errs.append("anchor_bar_index out of range")

    # bar structure
    prev_t: str | None = None
    for i, b in enumerate(bars):
        if not isinstance(b, dict):
            errs.append(f"bars[{i}] must be an object")
            continue
        miss = REQUIRED_BAR_KEYS - set(b.keys())
        if miss:
            errs.append(f"bars[{i}] missing keys: {sorted(miss)}")
        for k in ("open", "high", "low", "close"):
            if k in b:
                _, err = _as_float(b.get(k), f"bars[{i}].{k}")
                if err:
                    errs.append(err)
        ts = b.get("t") or b.get("timestamp")
        if not isinstance(ts, str) or not ts.strip():
            errs.append(f"bars[{i}] needs string 't' or 'timestamp'")
        else:
            if prev_t is not None and ts <= prev_t:
                errs.append(f"bars[{i}]: timestamps must be strictly increasing")
            prev_t = ts

    if errs:
        return WindowValidationResult(ok=False, errors=errs, point_in_time_safe=False)

    assert isinstance(idx, int)
    n = len(bars)
    context_len = idx + 1
    if context_len < min_context_bars_inclusive_anchor:
        errs.append(
            f"insufficient context: need at least {min_context_bars_inclusive_anchor} bars "
            f"through anchor (inclusive), got {context_len}"
        )

    forward_available = n - 1 - idx
    declared = window.get("bars_after_anchor_within_allowed_horizon")
    if declared is not None:
        if not isinstance(declared, int) or declared < 0:
            errs.append("bars_after_anchor_within_allowed_horizon must be a non-negative int")
        elif declared != forward_available:
            errs.append(
                f"bars_after_anchor_within_allowed_horizon ({declared}) != "
                f"actual forward bars ({forward_available})"
            )

    if forward_available > max_forward_bars:
        errs.append(
            f"forward bars {forward_available} exceed contract max_forward_bars={max_forward_bars}"
        )

    pit_flag = window.get("point_in_time_safe")
    pit_ok = True
    if pit_flag is False:
        pit_ok = False
    if window.get("forbidden_future_leak") is True:
        errs.append("window marked forbidden_future_leak — rejected for labeling")
        pit_ok = False

    if errs:
        return WindowValidationResult(ok=False, errors=errs, point_in_time_safe=pit_ok)

    return WindowValidationResult(ok=True, errors=[], point_in_time_safe=pit_ok)

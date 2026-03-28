"""Deterministic pattern predicates for level_interaction_rule_satisfaction_v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _tick_eps(L: float, tick_size: float | None, ticks: int, chop_rel: float) -> float:
    base = max(float(L) * chop_rel, 1e-12) if chop_rel > 0 else 1e-12
    if tick_size and tick_size > 0:
        return max(tick_size * ticks, base)
    return max(base, float(L) * 1e-6)


def _close(b: dict[str, Any]) -> float:
    return float(b["close"])


def _high(b: dict[str, Any]) -> float:
    return float(b["high"])


def _low(b: dict[str, Any]) -> float:
    return float(b["low"])


def _forward_range(anchor_idx: int, n_bars: int, max_h: int) -> range:
    end = min(n_bars - 1, anchor_idx + max_h)
    return range(anchor_idx + 1, end + 1)


def _has_streak_above(
    bars: list[dict[str, Any]],
    r: range,
    L: float,
    eps: float,
    n: int,
) -> bool:
    if n <= 0 or not r:
        return False
    hi = r.stop - 1
    for start in range(r.start, hi - n + 2):
        if start < 0:
            continue
        if start + n - 1 > hi:
            break
        ok = True
        for k in range(n):
            if _close(bars[start + k]) <= L + eps:
                ok = False
                break
        if ok:
            return True
    return False


def _has_streak_below(
    bars: list[dict[str, Any]],
    r: range,
    L: float,
    eps: float,
    n: int,
) -> bool:
    if n <= 0 or not r:
        return False
    hi = r.stop - 1
    for start in range(r.start, hi - n + 2):
        if start + 0 > hi:
            break
        if start + n - 1 > hi:
            break
        ok = True
        for k in range(n):
            if _close(bars[start + k]) >= L - eps:
                ok = False
                break
        if ok:
            return True
    return False


def _pierce_above(bars: list[dict[str, Any]], r: range, L: float, eps: float) -> int | None:
    for i in r:
        if _high(bars[i]) > L + eps:
            return i
    return None


def _pierce_below(bars: list[dict[str, Any]], r: range, L: float, eps: float) -> int | None:
    for i in r:
        if _low(bars[i]) < L - eps:
            return i
    return None


def _fail_below_after(
    bars: list[dict[str, Any]],
    start: int,
    end_inclusive: int,
    L: float,
    eps: float,
    m: int,
) -> bool:
    if m <= 0:
        return False
    for j in range(start, end_inclusive - m + 2):
        if j + m - 1 > end_inclusive:
            break
        ok = True
        for k in range(m):
            if _close(bars[j + k]) >= L - eps:
                ok = False
                break
        if ok:
            return True
    return False


def _fail_above_after(
    bars: list[dict[str, Any]],
    start: int,
    end_inclusive: int,
    L: float,
    eps: float,
    m: int,
) -> bool:
    for j in range(start, end_inclusive - m + 2):
        if j + m - 1 > end_inclusive:
            break
        ok = True
        for k in range(m):
            if _close(bars[j + k]) <= L + eps:
                ok = False
                break
        if ok:
            return True
    return False


def _touched_level(bars: list[dict[str, Any]], anchor_idx: int, r: range, L: float, eps: float) -> bool:
    for i in range(max(0, anchor_idx - 5), anchor_idx + 1):
        if i >= len(bars):
            break
        if _low(bars[i]) <= L + eps and _high(bars[i]) >= L - eps:
            return True
    for i in r:
        if _low(bars[i]) <= L + eps and _high(bars[i]) >= L - eps:
            return True
    return False


def _chop_only(bars: list[dict[str, Any]], r: range, L: float, band: float) -> bool:
    if not r:
        return False
    for i in r:
        if abs(_close(bars[i]) - L) > band:
            return False
    return True


@dataclass
class PatternAnalysis:
    has_acceptance_above: bool
    has_acceptance_below: bool
    fb_up: bool
    fb_down: bool
    rejection: bool
    no_setup: bool
    ambiguity_codes: list[str] = field(default_factory=list)
    matched_conditions: list[str] = field(default_factory=list)


def analyze_patterns(
    window: dict[str, Any],
    *,
    numeric: dict[str, Any],
) -> PatternAnalysis:
    """Pure deterministic predicates over OHLCV + level (post-validation)."""
    L = float(window["reference_level"])
    bars: list[dict[str, Any]] = window["bars"]
    anchor = int(window["anchor_bar_index"])
    approach = window.get("approach_direction") or "unknown"
    tick = window.get("tick_size")
    tick_f = float(tick) if tick is not None else None

    n_acc = int(numeric["persistence_closes_acceptance"])
    n_fail = int(numeric["persistence_closes_failure"])
    max_h = int(numeric["max_forward_bars"])
    chop_rel = float(numeric["chop_band_relative"])
    default_ticks = int(numeric["touch_tolerance_ticks_default"])
    level_rel = float(numeric.get("level_relative_epsilon", 0.0002))
    chop_close_rel = float(numeric.get("chop_close_band_relative", 0.00025))

    eps_gold = max(
        _tick_eps(L, tick_f, default_ticks, 0.0),
        float(L) * level_rel,
    )
    eps_heuristic = max(eps_gold * 1.5, _tick_eps(L, tick_f, default_ticks + 1, chop_rel))

    r = _forward_range(anchor, len(bars), max_h)
    end_i = r.stop - 1 if r else anchor

    has_acc_above = _has_streak_above(bars, r, L, eps_gold, n_acc)
    has_acc_below = _has_streak_below(bars, r, L, eps_gold, n_acc)

    p_up = _pierce_above(bars, r, L, eps_gold)
    fb_up = False
    if p_up is not None and not has_acc_above:
        fb_up = _fail_below_after(bars, p_up, end_i, L, eps_gold, n_fail)

    p_dn = _pierce_below(bars, r, L, eps_gold)
    fb_down = False
    if p_dn is not None and not has_acc_below:
        fb_down = _fail_above_after(bars, p_dn, end_i, L, eps_gold, n_fail)

    amb: list[str] = []
    if has_acc_above and has_acc_below:
        amb.append("MULTIPLE_PLAUSIBLE")

    approach_conflict = (
        approach == "unknown"
        and (
            (p_up is not None and _fail_below_after(bars, p_up, end_i, L, eps_heuristic, n_fail))
            and (p_dn is not None and _fail_above_after(bars, p_dn, end_i, L, eps_heuristic, n_fail))
        )
    )
    if approach_conflict:
        amb.append("APPROACH_CONFLICT")

    touched = _touched_level(bars, anchor, r, L, eps_gold)
    chop_band = float(L) * chop_close_rel

    allow_acc_above = approach in ("from_below", "unknown")
    allow_acc_below = approach in ("from_above", "unknown")

    eff_acc_above = has_acc_above and allow_acc_above
    eff_acc_below = has_acc_below and allow_acc_below

    rejection = (
        touched
        and not eff_acc_above
        and not eff_acc_below
        and not fb_up
        and not fb_down
        and not _chop_only(bars, r, L, chop_band)
    )

    no_setup = (
        not eff_acc_above
        and not eff_acc_below
        and not fb_up
        and not fb_down
        and not rejection
        and _chop_only(bars, r, L, chop_band)
    )

    conds: list[str] = []
    if eff_acc_above:
        conds.append("persistence_closes_above_level")
    if eff_acc_below:
        conds.append("persistence_closes_below_level")
    if fb_up:
        conds.append("pierce_above_then_fail_below")
    if fb_down:
        conds.append("pierce_below_then_fail_above")
    if rejection:
        conds.append("level_test_move_away_no_fb_or_acceptance")
    if no_setup:
        conds.append("chop_inside_band_no_catalog_pattern")

    return PatternAnalysis(
        has_acceptance_above=eff_acc_above,
        has_acceptance_below=eff_acc_below,
        fb_up=fb_up,
        fb_down=fb_down,
        rejection=rejection,
        no_setup=no_setup,
        ambiguity_codes=amb,
        matched_conditions=conds,
    )


def assign_by_decision_order(
    order: list[str],
    pa: PatternAnalysis,
) -> tuple[str, list[str]]:
    """First matching class in YAML order wins."""
    path: list[str] = []
    for cls in order:
        path.append(f"consider:{cls}")
        if cls == "ambiguous":
            if pa.ambiguity_codes:
                path.append("match:ambiguous")
                return "ambiguous", path
            path.append("skip:ambiguous_no_trigger")
            continue
        if cls == "false_breakout_up" and pa.fb_up:
            path.append("match:false_breakout_up")
            return "false_breakout_up", path
        if cls == "false_breakout_down" and pa.fb_down:
            path.append("match:false_breakout_down")
            return "false_breakout_down", path
        if cls == "acceptance_above" and pa.has_acceptance_above:
            path.append("match:acceptance_above")
            return "acceptance_above", path
        if cls == "acceptance_below" and pa.has_acceptance_below:
            path.append("match:acceptance_below")
            return "acceptance_below", path
        if cls == "rejection" and pa.rejection:
            path.append("match:rejection")
            return "rejection", path
        if cls == "no_setup" and pa.no_setup:
            path.append("match:no_setup")
            return "no_setup", path
    path.append("fallback:no_setup")
    return "no_setup", path

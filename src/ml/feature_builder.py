"""Point-in-time-safe feature computation (bars[0..anchor] only)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from ml.feature_spec_loader import load_feature_spec


def _eps_level(L: float, tick: float | None) -> float:
    t = float(tick) if tick and float(tick) > 0 else 0.0
    return max(t, float(L) * 0.0002)


def _lookback_end(anchor: int, max_lb: int) -> int:
    return max(0, anchor - max_lb + 1)


def _true_range(b: dict[str, Any], prev_close: float | None) -> float:
    h, l, c = float(b["high"]), float(b["low"]), float(b["close"])
    if prev_close is None:
        return h - l
    return max(h - l, abs(h - prev_close), abs(l - prev_close))


def compute_features(
    window: dict[str, Any],
    *,
    max_lookback_bars: int = 20,
) -> dict[str, Any]:
    """Compute all features declared in spec from window (PIT: indices <= anchor only)."""
    bars: list[dict[str, Any]] = window["bars"]
    a = int(window["anchor_bar_index"])
    L = float(window["reference_level"])
    tick = window.get("tick_size")
    eps = _eps_level(L, float(tick) if tick is not None else None)

    if a < 0 or a >= len(bars):
        raise ValueError("invalid anchor_bar_index")

    b_a = bars[a]
    o, h, l, c = float(b_a["open"]), float(b_a["high"]), float(b_a["low"]), float(b_a["close"])
    rng = max(h - l, 1e-12)

    close_distance_pct = (c - L) / L
    high_distance_pct = (h - L) / L
    low_distance_pct = (l - L) / L

    start = _lookback_end(a, max_lookback_bars)
    slice_bars = bars[start : a + 1]
    lookback_len = len(slice_bars)

    trs: list[float] = []
    pc: float | None = float(bars[start - 1]["close"]) if start > 0 else None
    for i in range(start, a + 1):
        trs.append(_true_range(bars[i], pc))
        pc = float(bars[i]["close"])
    atr_pct_14 = (sum(trs[-14:]) / min(len(trs), 14) / L) if trs else 0.0

    highs = [float(bars[i]["high"]) for i in range(start, a + 1)]
    lows = [float(bars[i]["low"]) for i in range(start, a + 1)]
    range_pct_lookback = (max(highs) - min(lows)) / L if highs else 0.0

    vol_regime_high = bool(atr_pct_14 > 0.002)

    body_pct_anchor = abs(c - o) / rng
    uc = max(o, c)
    lc = min(o, c)
    upper_wick_ratio_anchor = (h - uc) / rng
    lower_wick_ratio_anchor = (lc - l) / rng
    close_location_anchor = (c - l) / rng

    n_above = n_below = 0
    excess_series: list[float] = []
    for i in range(start, a + 1):
        cl = float(bars[i]["close"])
        excess_series.append(cl - L)
        if cl > L + eps:
            n_above += 1
        elif cl < L - eps:
            n_below += 1

    persistence_ratio_above_pre = n_above / lookback_len if lookback_len else 0.0

    reentry = 0
    for i in range(1, len(excess_series)):
        if excess_series[i - 1] * excess_series[i] < 0:
            reentry += 1

    closes_lb = [float(bars[i]["close"]) for i in range(start, a + 1)]
    if len(closes_lb) > 1:
        mu = sum(closes_lb) / len(closes_lb)
        var = sum((x - mu) ** 2 for x in closes_lb) / (len(closes_lb) - 1)
        consolidation_width_pct = math.sqrt(max(var, 0.0)) / L
    else:
        consolidation_width_pct = 0.0

    if len(closes_lb) >= 2:
        xs = list(range(len(closes_lb)))
        x_m = sum(xs) / len(xs)
        y_m = sum(closes_lb) / len(closes_lb)
        num = sum((xs[i] - x_m) * (closes_lb[i] - y_m) for i in range(len(xs)))
        den = sum((x - x_m) ** 2 for x in xs) or 1e-12
        pre_anchor_trend_slope = (num / den) / L
    else:
        pre_anchor_trend_slope = 0.0

    vols = [float(bars[i].get("volume", 0) or 0) for i in range(start, a + 1)]
    v_a = float(b_a.get("volume", 0) or 0)
    v_mean = sum(vols) / len(vols) if vols and sum(vols) > 0 else 0.0
    if v_mean > 0:
        volume_ratio_anchor = v_a / v_mean
        v_std = math.sqrt(
            max(0.0, sum((v - v_mean) ** 2 for v in vols) / max(len(vols) - 1, 1))
        )
        volume_zscore_anchor = (v_a - v_mean) / v_std if v_std > 1e-9 else 0.0
    else:
        volume_ratio_anchor = 1.0
        volume_zscore_anchor = 0.0

    ts = str(window.get("anchor_timestamp", ""))
    session_hour_bucket = "unknown"
    day_of_week = "unknown"
    if len(ts) >= 13 and "T" in ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            hr = dt.hour
            if hr < 10:
                session_hour_bucket = "morning"
            elif hr < 14:
                session_hour_bucket = "mid"
            elif hr < 18:
                session_hour_bucket = "afternoon"
            else:
                session_hour_bucket = "evening"
            day_of_week = dt.strftime("%A")
        except ValueError:
            pass

    return {
        "close_distance_pct": close_distance_pct,
        "high_distance_pct": high_distance_pct,
        "low_distance_pct": low_distance_pct,
        "atr_pct_14": atr_pct_14,
        "range_pct_lookback": range_pct_lookback,
        "vol_regime_high": vol_regime_high,
        "body_pct_anchor": body_pct_anchor,
        "upper_wick_ratio_anchor": upper_wick_ratio_anchor,
        "lower_wick_ratio_anchor": lower_wick_ratio_anchor,
        "close_location_anchor": close_location_anchor,
        "n_closes_above_level_pre": n_above,
        "n_closes_below_level_pre": n_below,
        "persistence_ratio_above_pre": persistence_ratio_above_pre,
        "reentry_through_level_pre": reentry,
        "consolidation_width_pct": consolidation_width_pct,
        "pre_anchor_trend_slope": pre_anchor_trend_slope,
        "volume_ratio_anchor": volume_ratio_anchor,
        "volume_zscore_anchor": volume_zscore_anchor,
        "session_hour_bucket": session_hour_bucket,
        "day_of_week": day_of_week,
        "htf_alignment_placeholder": 0.0,
    }


def _windows_dir(d: Path) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for p in sorted(d.glob("*.json")):
        out.append((p.stem, json.loads(p.read_text(encoding="utf-8"))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build feature rows from market windows (Step 7)")
    ap.add_argument("--ml-root", type=Path, default=Path("ml"))
    ap.add_argument("--windows-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("ml_output/step7/feature_rows.jsonl"))
    args = ap.parse_args()
    ml_root = args.ml_root.resolve()
    spec_path = ml_root / "feature_spec.yaml"
    try:
        spec = load_feature_spec(spec_path)
    except Exception as e:
        print(f"ERROR: spec: {e}", file=sys.stderr)
        return 1
    max_lb = int(spec.get("observation_window", {}).get("max_lookback_bars", 20))
    wdir = (args.windows_dir or (ml_root / "fixtures" / "market_windows")).resolve()
    if not wdir.is_dir():
        print(f"ERROR: missing {wdir}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for stem, w in _windows_dir(wdir):
            try:
                feats = compute_features(w, max_lookback_bars=max_lb)
            except Exception as e:
                print(f"WARN: skip {stem}: {e}", file=sys.stderr)
                continue
            row = {"candidate_id": w.get("candidate_id", stem), "features": feats}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

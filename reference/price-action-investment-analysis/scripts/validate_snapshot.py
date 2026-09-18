#!/usr/bin/env python3
"""Validate a portable, closed-candle analysis snapshot from stdin."""

from __future__ import annotations

import json
import math
import sys
from typing import Any


def emit(payload: dict[str, Any], code: int) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def main() -> None:
    try:
        snapshot = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        emit({"valid": False, "errors": [f"invalid JSON: {exc.msg}"]}, 2)

    errors: list[str] = []
    if not isinstance(snapshot, dict):
        emit({"valid": False, "errors": ["snapshot must be a JSON object"]}, 2)
    for field in ("symbol", "timeframe"):
        if not isinstance(snapshot.get(field), str) or not snapshot[field].strip():
            errors.append(f"{field} must be a non-empty string")
    bars = snapshot.get("bars")
    if not isinstance(bars, list):
        errors.append("bars must be a list")
        bars = []
    if len(bars) < 20:
        errors.append("at least 20 closed bars are required")

    for index, bar in enumerate(bars):
        label = f"bars[{index}]"
        if not isinstance(bar, dict):
            errors.append(f"{label} must be an object")
            continue
        expected_seq = index + 1
        if bar.get("seq") != expected_seq:
            errors.append(f"{label}.seq must be {expected_seq} (newest-first consecutive order)")
        if bar.get("closed") is not True:
            errors.append(f"{label}.closed must be true")
        missing = [
            key for key in ("open", "high", "low", "close") if not finite_number(bar.get(key))
        ]
        if missing:
            errors.append(f"{label} has missing/non-finite OHLC: {', '.join(missing)}")
            continue
        high, low, close = bar["high"], bar["low"], bar["close"]
        if high < low:
            errors.append(f"{label}.high must be >= low")
        if close < low or close > high:
            errors.append(f"{label}.close must be within [low, high]")

    indicators = snapshot.get("indicators")
    if indicators is not None and not isinstance(indicators, dict):
        errors.append("indicators must be an object when supplied")
    elif isinstance(indicators, dict):
        for name in ("ema20", "atr14"):
            values = indicators.get(name)
            if values is not None and (not isinstance(values, list) or len(values) != len(bars)):
                errors.append(f"indicators.{name} must align with bars when supplied")

    emit(
        {
            "valid": not errors,
            "errors": errors,
            "summary": {
                "symbol": snapshot.get("symbol"),
                "timeframe": snapshot.get("timeframe"),
                "bar_count": len(bars),
                "newest_bar": "K1" if bars else None,
            },
        },
        0 if not errors else 2,
    )


if __name__ == "__main__":
    main()

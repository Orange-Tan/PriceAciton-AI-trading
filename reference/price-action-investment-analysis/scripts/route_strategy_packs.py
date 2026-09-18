#!/usr/bin/env python3
"""Route validated Stage 1 diagnosis JSON to portable strategy-pack IDs."""

from __future__ import annotations

import json
import sys
from typing import Any

CHANNELS = {"micro_channel", "tight_channel", "normal_channel", "broad_channel"}
RANGES = {"trading_range", "trending_tr"}
PATTERN_PACKS = {
    "wedge": "wedge",
    "reversal_attempt": "reversal",
    "mtr": "reversal",
    "final_flag": "reversal",
    "h1": "h1h2l1l2",
    "h2": "h1h2l1l2",
    "l1": "h1h2l1l2",
    "l2": "h1h2l1l2",
    "breakout_test": "breakout-failure",
    "breakout_pullback": "breakout-failure",
    "breakout_failure": "breakout-failure",
    "failed_breakout": "breakout-failure",
    "always_in": "always-in",
    "ail": "always-in",
    "ais": "always-in",
    "20gb": "always-in",
    "gap_bar": "always-in",
    "barbwire": "barbwire",
    "wire": "barbwire",
    "overlap": "barbwire",
    "middle_range": "barbwire",
    "failed_signal": "magnet",
    "magnet": "magnet",
    "trapped_traders": "magnet",
    "ascending_triangle": "triangle",
    "descending_triangle": "triangle",
    "symmetrical_triangle": "triangle",
    "expanding_triangle": "triangle",
    "double_top_bottom": "double-top-bottom",
}


def main() -> None:
    try:
        stage1: Any = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON: {exc.msg}"}, ensure_ascii=False))
        raise SystemExit(2)
    if not isinstance(stage1, dict):
        print(json.dumps({"error": "Stage 1 must be a JSON object"}, ensure_ascii=False))
        raise SystemExit(2)

    cycle = str(stage1.get("cycle_position", "unknown"))
    direction = str(stage1.get("direction", "neutral"))
    patterns = [
        str(value).lower()
        for value in stage1.get("detected_patterns", [])
        if isinstance(value, str)
    ]
    if stage1.get("gate_result") == "wait" or cycle in {"unknown", "extreme_tr"}:
        print(
            json.dumps(
                {
                    "strategy_packs": [],
                    "reasons": ["Stage 1 gate blocks Stage 2"],
                    "direction": direction,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    packs: list[str] = ["core-decision"]
    reasons: list[str] = ["all passing Stage 1 diagnoses require core-decision"]
    if cycle in CHANNELS:
        packs.append("trend-channel")
        reasons.append(f"cycle_position={cycle}")
    elif cycle == "spike":
        packs.append("spike")
        reasons.append("cycle_position=spike")
    elif cycle in RANGES:
        packs.append("trading-range")
        reasons.append(f"cycle_position={cycle}")
    for pattern in patterns:
        pack = PATTERN_PACKS.get(pattern)
        if pack and pack not in packs:
            packs.append(pack)
            reasons.append(f"detected_patterns contains {pattern}")
    print(
        json.dumps(
            {"strategy_packs": packs, "reasons": reasons, "direction": direction},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

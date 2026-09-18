#!/usr/bin/env python3
"""Validate the portable minimum contract for Stage 1 and Stage 2 JSON."""

from __future__ import annotations

import json
import sys
from typing import Any

STAGE1_REQUIRED = {
    "cycle_position",
    "direction",
    "diagnosis_confidence",
    "detected_patterns",
    "key_signals",
    "support_levels",
    "resistance_levels",
    "bar_analysis",
    "bar_by_bar_summary",
    "gate_trace",
    "gate_result",
}
STAGE2_REQUIRED = {"decision", "decision_trace", "watch_points", "terminal"}


def invalid(message: str) -> None:
    print(json.dumps({"valid": False, "errors": [message]}, ensure_ascii=False, indent=2))
    raise SystemExit(2)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"stage1", "stage2"}:
        invalid("usage: validate_analysis_result.py stage1|stage2 < result.json")
    stage = sys.argv[1]
    try:
        result: Any = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        invalid(f"invalid JSON: {exc.msg}")
    if not isinstance(result, dict):
        invalid("result must be a JSON object")

    errors: list[str] = []
    required = STAGE1_REQUIRED if stage == "stage1" else STAGE2_REQUIRED
    errors.extend(f"missing required field: {key}" for key in sorted(required - result.keys()))

    if stage == "stage1":
        if result.get("direction") not in {"bullish", "bearish", "neutral"}:
            errors.append("direction must be bullish, bearish, or neutral")
        if result.get("gate_result") not in {"proceed", "wait"}:
            errors.append("gate_result must be proceed or wait")
        if not isinstance(result.get("gate_trace"), list):
            errors.append("gate_trace must be a list")
        if result.get("gate_result") == "wait" and result.get("cycle_position") not in {
            "unknown",
            "extreme_tr",
        }:
            errors.append("gate_result=wait requires cycle_position unknown or extreme_tr")
    else:
        decision = result.get("decision")
        terminal = result.get("terminal")
        if not isinstance(decision, dict):
            errors.append("decision must be an object")
        if not isinstance(terminal, dict):
            errors.append("terminal must be an object")
        if isinstance(decision, dict):
            action = decision.get("action")
            if action not in {"trade", "wait", "reject"}:
                errors.append("decision.action must be trade, wait, or reject")
            price_fields = ("entry_price", "stop_loss_price", "take_profit_price")
            if action == "trade" and any(decision.get(field) is None for field in price_fields):
                errors.append("trade requires entry_price, stop_loss_price, and take_profit_price")
            if action in {"wait", "reject"} and any(
                decision.get(field) is not None for field in price_fields
            ):
                errors.append("wait/reject requires null entry, stop, and target prices")
        if (
            isinstance(decision, dict)
            and isinstance(terminal, dict)
            and terminal.get("outcome") != decision.get("action")
        ):
            errors.append("terminal.outcome must equal decision.action")

    print(
        json.dumps(
            {"valid": not errors, "errors": errors, "stage": stage}, ensure_ascii=False, indent=2
        )
    )
    raise SystemExit(0 if not errors else 2)


if __name__ == "__main__":
    main()

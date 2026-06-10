"""Helpers to merge stage-2 JSON for UI panels."""
from __future__ import annotations

import copy
from typing import Any


def merge_stage2_for_panels(s2_full: dict[str, Any] | None) -> dict[str, Any]:
    """Merge top-level prediction fields into the inner decision dict for panels."""
    if not isinstance(s2_full, dict):
        return {}
    inner = s2_full.get("decision")
    payload: dict[str, Any] = dict(inner) if isinstance(inner, dict) else {}
    for key in ("next_bar_prediction", "next_cycle_prediction"):
        if key in s2_full:
            payload[key] = s2_full[key]
    return payload


def prepare_stage2_for_ui(
    s2_full: dict[str, Any] | None,
    *,
    stage1_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize / synthesize predictions for display (e.g. demo replay of old records)."""
    if not isinstance(s2_full, dict):
        return {}
    out = copy.deepcopy(s2_full)
    from pa_agent.ai.stage2_normalizer import ensure_stage2_predictions

    ensure_stage2_predictions(out, stage1_json=stage1_json)
    return merge_stage2_for_panels(out)

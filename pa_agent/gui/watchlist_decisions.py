"""Extract compact watchlist decisions from completed analysis records."""

from __future__ import annotations

from datetime import date
from typing import Any


def decision_for_record(record: Any) -> tuple[str, date | None]:
    """Return ``(买入/卖出/观望, record_day)`` or empty values when unavailable."""
    stage2 = getattr(record, "stage2_decision", None)
    if not isinstance(stage2, dict):
        return "", None
    decision = stage2.get("decision")
    if not isinstance(decision, dict):
        return "", None
    order_type = str(decision.get("order_type", "") or "")
    direction = str(decision.get("order_direction", "") or "")
    if order_type == "不下单":
        text = "观望"
    elif any(mark in direction for mark in ("多", "买")):
        text = "买入"
    elif any(mark in direction for mark in ("空", "卖")):
        text = "卖出"
    else:
        text = ""
    meta = getattr(record, "meta", None)
    raw_timestamp = str(getattr(meta, "timestamp_local_iso", "") or "")
    try:
        record_day = date.fromisoformat(raw_timestamp[:10])
    except ValueError:
        record_day = None
    return text, record_day

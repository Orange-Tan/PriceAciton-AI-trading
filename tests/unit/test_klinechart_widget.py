from __future__ import annotations

from pa_agent.data.base import IndicatorBundle, KlineBar, KlineFrame
from pa_agent.gui.klinechart_widget import (
    decision_to_klinechart_overlays,
    frame_to_klinechart_bars,
    levels_to_klinechart_overlays,
)


def _frame() -> KlineFrame:
    return KlineFrame(
        symbol="XAUUSD",
        timeframe="1h",
        bars=(
            KlineBar(1, 1_700_000_000_000, 11, 12, 10, 11.5, 120),
            KlineBar(2, 1_699_996_400_000, 10, 11, 9, 10.5, 100),
        ),
        indicators=IndicatorBundle(ema20=(11.0, 10.0), atr14=(1.0, 1.0)),
        snapshot_ts_local_ms=1_700_000_000_000,
    )


def test_frame_payload_is_ascending_and_contains_ohlcv() -> None:
    bars = frame_to_klinechart_bars(_frame())

    assert [bar["timestamp"] for bar in bars] == [1_699_996_400_000, 1_700_000_000_000]
    assert bars[0]["open"] == 10.0
    assert bars[1]["close"] == 11.5
    assert bars[0]["volume"] == 100.0


def test_empty_frame_payload_is_empty() -> None:
    frame = _frame()
    empty = KlineFrame(
        symbol=frame.symbol,
        timeframe=frame.timeframe,
        bars=(),
        indicators=IndicatorBundle(ema20=(), atr14=()),
        snapshot_ts_local_ms=frame.snapshot_ts_local_ms,
    )
    assert frame_to_klinechart_bars(empty) == []


def test_program_overlays_map_levels_and_trade_decision() -> None:
    levels = [
        type(
            "Level",
            (),
            {"kind": "support", "price": 9.5, "low": 9.0, "high": 10.0, "label": "支撑"},
        )()
    ]
    level_items = levels_to_klinechart_overlays(levels, _frame())
    decision_items = decision_to_klinechart_overlays(
        {
            "order_type": "限价单",
            "order_direction": "做多",
            "entry_price": 11.0,
            "take_profit_price": 12.0,
            "take_profit_price_2": 13.0,
            "stop_loss_price": 10.0,
        },
        _frame(),
    )

    assert level_items[0]["type"] == "level"
    assert level_items[0]["price"] == 9.5
    assert {item["label"] for item in decision_items if item["type"] == "level"} == {
        "Entry",
        "TP1",
        "TP2",
        "SL",
    }
    assert any(item["type"] == "marker" and item["text"] == "Buy" for item in decision_items)


def test_no_order_has_no_program_decision_overlays() -> None:
    assert decision_to_klinechart_overlays({"order_type": "不下单"}, _frame()) == []

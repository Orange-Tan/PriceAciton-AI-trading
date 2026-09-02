from __future__ import annotations

from pa_agent.data.base import IndicatorBundle, KlineBar, KlineFrame
from pa_agent.data.tradingview_udf import frame_to_udf_history, udf_config


def _frame() -> KlineFrame:
    bars = (
        KlineBar(1, 1700000123456, 11, 12, 10, 11.5, 120),
        KlineBar(2, 1700000060000, 10, 11, 9, 10.5, 100),
    )
    return KlineFrame(
        symbol="600519",
        timeframe="1d",
        bars=bars,
        indicators=IndicatorBundle(ema20=(11.0, 10.0), atr14=(1.0, 1.0)),
        snapshot_ts_local_ms=1700000200000,
    )


def test_frame_to_udf_history_is_ascending_and_uses_seconds() -> None:
    payload = frame_to_udf_history(_frame())

    assert payload["s"] == "ok"
    assert payload["t"] == [1700000060, 1700000123]
    assert payload["o"] == [10.0, 11.0]
    assert payload["h"] == [11.0, 12.0]
    assert payload["l"] == [9.0, 10.0]
    assert payload["c"] == [10.5, 11.5]
    assert payload["v"] == [100.0, 120.0]


def test_udf_config_exposes_supported_resolutions() -> None:
    config = udf_config()

    assert config["supports_search"] is True
    assert "1D" in config["supported_resolutions"]
    assert config["supports_time"] is True

"""Pure-logic unit tests for 通达信 (tdx) and 腾讯财经 (tencent) sources.

No network / no Qt: only symbol normalisation, volume-unit conversion and
row-building helpers shared by the two sources.
"""
from __future__ import annotations

import pytest

from pa_agent.data.tdx_source import (
    TdxSource,
    _market_for_prefixed,
    _tdx_bar_to_row,
    ashare_prefixed_code,
)


# ── 通达信 ────────────────────────────────────────────────────────────────────


def test_ashare_prefixed_code_rules() -> None:
    assert ashare_prefixed_code("600519") == "sh600519"
    assert ashare_prefixed_code("000001") == "sz000001"
    assert ashare_prefixed_code("000300") == "sh000300"  # 上证指数
    assert ashare_prefixed_code("399006") == "sz399006"  # 深证指数
    assert ashare_prefixed_code("sh600519") == "sh600519"
    assert ashare_prefixed_code("000001.SZ") == "sz000001"


def test_market_for_prefixed() -> None:
    assert _market_for_prefixed("sh600519") == 1
    assert _market_for_prefixed("sz000001") == 0


def test_tdx_bar_to_row_volume_scale() -> None:
    bar = {
        "datetime": "2026-08-21 15:00",
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "vol": 100.0,
        "amount": 12345.0,
    }
    # 日线：vol 已是股，不缩放
    daily = _tdx_bar_to_row(bar)
    assert daily["volume"] == 100.0
    assert daily["amount"] == 12345.0
    # 周线/月线：vol 是手，×100
    weekly = _tdx_bar_to_row(bar, volume_scale=100.0)
    assert weekly["volume"] == 10000.0


def test_tdx_supported_timeframes() -> None:
    src = TdxSource()
    assert src.supported_timeframes() == [
        "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M",
    ]


def test_tdx_subscribe_rejects_bad_timeframe() -> None:
    src = TdxSource()
    with pytest.raises(ValueError):
        src.subscribe("600519", "2m")


def test_tdx_subscribe_rejects_invalid_symbol() -> None:
    src = TdxSource()
    with pytest.raises(ValueError):
        src.subscribe("XAUUSD", "1d")


# ── 腾讯财经 ──────────────────────────────────────────────────────────────────


from pa_agent.data.tencent_source import (  # noqa: E402
    TencentSource,
    _normalize_tencent_time,
    _row_from_tencent,
)


def test_tencent_time_normalization() -> None:
    assert _normalize_tencent_time("20260827") == "2026-08-27"
    assert _normalize_tencent_time("202608271400") == "2026-08-27 14:00"
    assert _normalize_tencent_time("20260827140000") == "2026-08-27 14:00:00"
    assert _normalize_tencent_time("2026-08-27") == "2026-08-27"
    assert _normalize_tencent_time(202608271400) == "2026-08-27 14:00"


def test_tencent_row_stock_volume_lots_to_shares() -> None:
    # [时间, 开, 收, 高, 低, 成交量(手)]
    row = _row_from_tencent(["2026-08-27", "1280", "1290", "1300", "1270", "24767"], "sh600519")
    assert row["volume"] == 2476700.0  # 手 → 股


def test_tencent_row_index_volume_unchanged() -> None:
    row = _row_from_tencent(["2026-08-27", "4500", "4630", "4650", "4490", "202017248"], "sh000300")
    assert row["volume"] == 202017248.0  # 指数原值，不换算


def test_tencent_supported_timeframes() -> None:
    src = TencentSource()
    assert src.supported_timeframes() == [
        "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M",
    ]


def test_tencent_subscribe_rejects_invalid_symbol() -> None:
    src = TencentSource()
    with pytest.raises(ValueError):
        src.subscribe("XAUUSD", "1d")


@pytest.mark.parametrize("source_cls", [TdxSource, TencentSource])
def test_apply_spot_reuses_supplied_quote(monkeypatch, source_cls) -> None:
    src = source_cls()
    monkeypatch.setattr(src, "_fetch_quote", lambda symbol: (_ for _ in ()).throw(AssertionError("duplicate quote")))
    rows = [{"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 0.0, "amount": 0.0}]
    src._apply_spot_to_forming(
        rows,
        daily=False,
        quote={"price": 11.0, "open": 10.0, "high": 11.0, "low": 9.0, "vol": 2.0, "amount": 3.0, "prev_close": 10.0},
    )
    assert rows[0]["close"] == 11.0

"""TradingView outbound connectivity probe."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import sys
import time
import types

from pa_agent.data.tradingview_connectivity import check_tradingview_connectivity

# Keep connectivity tests runnable when the optional tvDatafeed package is not
# installed; production code still reports ImportError normally.
sys.modules.setdefault(
    "tvDatafeed",
    types.SimpleNamespace(Interval=MagicMock(), TvDatafeed=MagicMock()),
)


def test_probe_once_returns_promptly_on_timeout(monkeypatch) -> None:
    from pa_agent.data import tradingview_connectivity as connectivity

    class Interval:
        in_1_minute = object()

    class SlowTv:
        def get_hist(self, **kwargs):
            time.sleep(0.5)
            return object()

    monkeypatch.setitem(
        sys.modules,
        "tvDatafeed",
        types.SimpleNamespace(Interval=Interval, TvDatafeed=SlowTv),
    )
    started = time.monotonic()
    result = connectivity._probe_once(timeout_s=0.01)

    assert result == (False, "连接超时", True)
    assert time.monotonic() - started < 0.15


def _mock_tv_ok() -> tuple[MagicMock, MagicMock]:
    mock_df = MagicMock()
    mock_df.empty = False
    mock_interval = MagicMock()
    mock_interval.in_1_minute = object()
    return mock_interval, mock_df


def test_check_tradingview_connectivity_ok() -> None:
    mock_interval, mock_df = _mock_tv_ok()
    with (
        patch("tvDatafeed.Interval", mock_interval),
        patch("tvDatafeed.TvDatafeed") as tv_cls,
    ):
        tv_cls.return_value.get_hist.return_value = mock_df
        ok, detail = check_tradingview_connectivity(
            timeout_s=5.0, max_attempts=3, retry_delay_s=0.0
        )
    assert ok is True
    assert detail is None


def test_check_tradingview_connectivity_empty_data() -> None:
    mock_df = MagicMock()
    mock_df.empty = True
    mock_interval = MagicMock()
    mock_interval.in_1_minute = object()
    with (
        patch("tvDatafeed.Interval", mock_interval),
        patch("tvDatafeed.TvDatafeed") as tv_cls,
    ):
        tv_cls.return_value.get_hist.return_value = mock_df
        ok, detail = check_tradingview_connectivity(
            timeout_s=5.0, max_attempts=1, retry_delay_s=0.0
        )
    assert ok is False
    assert detail


def test_check_tradingview_connectivity_retries_then_succeeds() -> None:
    mock_interval, mock_df = _mock_tv_ok()
    side_effects = [RuntimeError("transient"), mock_df]
    with (
        patch("tvDatafeed.Interval", mock_interval),
        patch("tvDatafeed.TvDatafeed") as tv_cls,
        patch("pa_agent.data.tradingview_connectivity.time.sleep"),
    ):
        tv_cls.return_value.get_hist.side_effect = side_effects
        ok, detail = check_tradingview_connectivity(
            timeout_s=5.0, max_attempts=3, retry_delay_s=0.0
        )
    assert ok is True
    assert detail is None
    assert tv_cls.return_value.get_hist.call_count == 2


def test_check_tradingview_connectivity_exhausts_retries() -> None:
    mock_interval = MagicMock()
    mock_interval.in_1_minute = object()
    with (
        patch("tvDatafeed.Interval", mock_interval),
        patch("tvDatafeed.TvDatafeed") as tv_cls,
        patch("pa_agent.data.tradingview_connectivity.time.sleep"),
    ):
        tv_cls.return_value.get_hist.side_effect = RuntimeError("still down")
        ok, detail = check_tradingview_connectivity(
            timeout_s=5.0, max_attempts=3, retry_delay_s=0.0
        )
    assert ok is False
    assert detail is not None
    assert "已自动重试 3 次" in detail
    assert tv_cls.return_value.get_hist.call_count == 3

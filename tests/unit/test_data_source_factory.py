"""Tests for data source factory and settings."""
from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError

from pa_agent.config.settings import GeneralSettings
from pa_agent.data.factory import (
    DATA_SOURCE_CHOICES,
    create_data_source,
    default_symbol_for_kind,
    default_tradingview_exchange,
    normalize_data_source_kind,
)
from pa_agent.data.eastmoney_source import EastMoneySource
from pa_agent.data.tushare_source import TushareSource
from pa_agent.data.tradingview import TradingViewSource


def test_normalize_data_source_kind_defaults_unknown():
    assert normalize_data_source_kind("invalid") == "tradingview"
    assert normalize_data_source_kind(None) == "tradingview"


def test_normalize_data_source_kind_all_sources():
    assert normalize_data_source_kind("akshare") == "akshare"
    assert normalize_data_source_kind("eastmoney") == "eastmoney"
    assert normalize_data_source_kind("tushare") == "tushare"
    assert normalize_data_source_kind("tdx") == "tdx"
    assert normalize_data_source_kind("tencent") == "tencent"


def test_all_sources_in_ui_choices():
    ui_kinds = {k for k, _ in DATA_SOURCE_CHOICES}
    assert ui_kinds == {
        "tradingview",
        "akshare",
        "eastmoney",
        "tushare",
        "tdx",
        "tencent",
    }


def test_create_data_source_returns_expected_types():
    assert isinstance(create_data_source("tradingview"), TradingViewSource)
    assert isinstance(create_data_source("eastmoney"), EastMoneySource)
    assert isinstance(create_data_source("tushare"), TushareSource)


def test_default_symbols_per_kind():
    assert default_symbol_for_kind("tradingview") == "XAUUSD"
    assert default_symbol_for_kind("eastmoney") == "000001"
    assert default_symbol_for_kind("tushare") == "000001"
    assert default_symbol_for_kind("tdx") == "000001"
    assert default_symbol_for_kind("tencent") == "000001"


def test_default_tradingview_exchange_is_auto():
    assert default_tradingview_exchange() == ""


def test_general_settings_last_data_source_default():
    g = GeneralSettings()
    assert g.last_data_source == "tradingview"


def test_probe_timeout_cancels_future(monkeypatch):
    import pa_agent.data.factory as factory

    calls = []

    class Future:
        def result(self, timeout):
            raise FutureTimeoutError

        def cancel(self):
            calls.append("cancel")

    class Executor:
        def submit(self, fn):
            return Future()

        def shutdown(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(factory, "ThreadPoolExecutor", lambda **kwargs: Executor())
    ok, detail = factory.probe_data_source("tencent", timeout_s=0.01)

    assert ok is False
    assert "cancel" in calls
    assert {"wait": False, "cancel_futures": True} in calls

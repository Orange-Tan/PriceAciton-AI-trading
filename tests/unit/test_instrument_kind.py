from __future__ import annotations

from types import SimpleNamespace

import pytest

from pa_agent.gui.instrument_kind import infer_instrument_kind


@pytest.mark.parametrize(
    ("symbol", "data_source", "exchange", "bars", "expected"),
    [
        ("600519", "eastmoney", "", None, "股票"),
        ("SPX", "tradingview", "SP", None, "指数"),
        ("XAUUSD", "OANDA", "", None, "贵金属"),
        ("EURUSD", "FOREXCOM", "", None, "外汇"),
        ("BTCUSDT", "binance", "", None, "加密货币"),
        ("CL1!", "NYMEX", "", None, "期货"),
        ("mystery", "unknown", "", None, "其他"),
    ],
)
def test_infer_instrument_kind(symbol, data_source, exchange, bars, expected):
    assert infer_instrument_kind(
        symbol,
        data_source=data_source,
        exchange=exchange,
        bars=bars,
    ) == expected


def test_infer_instrument_kind_prefers_explicit_bar_metadata() -> None:
    bars = SimpleNamespace(instrument_kind="外汇")

    assert infer_instrument_kind(
        "BTCUSDT",
        data_source="binance",
        exchange="",
        bars=bars,
    ) == "外汇"


def test_infer_instrument_kind_uses_tradingview_index_prefix() -> None:
    assert infer_instrument_kind(
        "SPX",
        data_source="tradingview",
        exchange="",
        bars=None,
    ) == "指数"


def test_infer_instrument_kind_bar_metadata_beats_symbol_rule() -> None:
    bars = {"security_type": "crypto"}

    assert infer_instrument_kind(
        "600519",
        data_source="eastmoney",
        exchange="",
        bars=bars,
    ) == "加密货币"


def test_infer_instrument_kind_bar_sequence_metadata_beats_symbol_rule() -> None:
    bars = [{"kind": "equity"}]

    assert infer_instrument_kind(
        "BTCUSDT",
        data_source="unknown",
        exchange="",
        bars=bars,
    ) == "股票"


@pytest.mark.parametrize("bars", ["crypto", b"crypto"])
def test_infer_instrument_kind_handles_string_like_bars_without_recursing(bars) -> None:
    assert infer_instrument_kind(
        "mystery",
        data_source="unknown",
        exchange="",
        bars=bars,
    ) == "其他"


def test_infer_instrument_kind_treats_usdtry_as_forex() -> None:
    assert infer_instrument_kind(
        "USDTRY",
        data_source="unknown",
        exchange="",
        bars=None,
    ) == "外汇"


def test_infer_instrument_kind_crypto_source_beats_metal_symbol() -> None:
    assert infer_instrument_kind(
        "XAUUSD",
        data_source="binance",
        exchange="",
        bars=None,
    ) == "加密货币"

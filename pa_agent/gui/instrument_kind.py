from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_KIND_ALIASES = {
    "stock": "股票",
    "equity": "股票",
    "share": "股票",
    "a股": "股票",
    "ashare": "股票",
    "index": "指数",
    "crypto": "加密货币",
    "cryptocurrency": "加密货币",
    "forex": "外汇",
    "fx": "外汇",
    "metal": "贵金属",
    "precious_metal": "贵金属",
    "future": "期货",
    "futures": "期货",
    "股票": "股票",
    "指数": "指数",
    "加密货币": "加密货币",
    "外汇": "外汇",
    "贵金属": "贵金属",
    "期货": "期货",
}

_CRYPTO_DATA_SOURCES = {"BINANCE", "BYBIT", "OKX", "COINBASE", "KRAKEN"}
_CRYPTO_SUFFIXES = ("USDT", "USDC", "BTC", "ETH", "BUSD", "FDUSD")
_METAL_SYMBOLS = {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"}
_FOREX_PAIRS = {
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "EURJPY",
    "EURGBP",
    "EURCHF",
    "GBPJPY",
    "GBPCHF",
    "AUDJPY",
    "NZDJPY",
}
_FUTURES_EXCHANGES = {"NYMEX", "CME", "CBOT", "COMEX", "SHFE", "DCE", "CZCE", "INE"}
_INDEX_EXCHANGES = {"SP", "SPX", "INDEX", "TVC", "FOREXCOM"}


def infer_instrument_kind(
    symbol: str,
    *,
    data_source: str = "",
    exchange: str = "",
    bars: object | None = None,
) -> str:
    kind = _kind_from_bars(bars)
    if kind is not None:
        return kind

    sym = _clean(symbol)
    ds = _clean(data_source)
    ex = _clean(exchange)

    if ds in _CRYPTO_DATA_SOURCES or ex in _CRYPTO_DATA_SOURCES:
        return "加密货币"
    if sym.endswith(_CRYPTO_SUFFIXES) and sym not in _METAL_SYMBOLS and sym not in _FOREX_PAIRS:
        return "加密货币"
    if sym in _METAL_SYMBOLS:
        return "贵金属"
    if ds in {"OANDA", "FOREXCOM"} or ex in {"OANDA", "FOREXCOM"}:
        return "外汇"
    if len(sym) == 6 and sym.isalpha() and (sym in _FOREX_PAIRS or sym.endswith("TRY")):
        return "外汇"
    if ex in _FUTURES_EXCHANGES or sym.endswith(("!", "_F", "-F")):
        return "期货"
    if ex in _INDEX_EXCHANGES or (ds == "TRADINGVIEW" and sym in {"SPX", "DJI", "NDX", "IXIC", "HSI"}):
        return "指数"
    if len(sym) == 6 and sym.isdigit() and sym.startswith(("0", "3", "6")):
        return "股票"
    return "其他"


def _kind_from_bars(bars: object | None) -> str | None:
    if bars is None:
        return None

    candidates: tuple[Any, ...]
    if isinstance(bars, dict):
        candidates = (
            bars.get("instrument_kind"),
            bars.get("kind"),
            bars.get("asset_class"),
            bars.get("market_kind"),
            bars.get("security_type"),
        )
    else:
        candidates = (
            getattr(bars, "instrument_kind", None),
            getattr(bars, "kind", None),
            getattr(bars, "asset_class", None),
            getattr(bars, "market_kind", None),
            getattr(bars, "security_type", None),
        )

    for raw in candidates:
        kind = _normalize_kind(raw)
        if kind is not None:
            return kind

    if isinstance(bars, Sequence) and not isinstance(bars, (str, bytes, bytearray)) and bars:
        return _kind_from_bars(bars[0])

    return None


def _normalize_kind(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    return _KIND_ALIASES.get(text)


def _clean(value: Any) -> str:
    return str(value or "").strip().upper()

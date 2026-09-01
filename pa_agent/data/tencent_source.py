"""腾讯财经（腾讯行情）A 股 K 线数据源 —— 纯 HTTP，无需 token。

接口（均为公开免费行情）：
- 日/周/月 K 线：``web.ifzq.gtimg.cn/appstock/app/fqkline/get``（前复权）
- 分钟 K 线：``web.ifzq.gtimg.cn/appstock/app/kline/mkline``
- 实时报价：``qt.gtimg.cn/q=``

K 线行格式（fqkline 与 mkline 一致）：``[时间, 开, 收, 高, 低, 成交量(手)]``。
个股成交量换算为「股」、指数保持原值，统一复用 ``quote_volume_lots_to_shares``。
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from pa_agent.data.ashare_common import (
    apply_session_quote_to_forming_row,
    ashare_head_bar_live,
    ashare_session_open,
    ashare_trading_day,
    ensure_today_forming_daily_bar,
    normalize_ashare_symbol,
    quote_volume_lots_to_shares,
    resample_rows_to_4h,
    row_time_to_ts_ms,
    rows_to_kline_bars,
)
from pa_agent.data.base import DataSource, DataSourceTransientError, KlineBar
from pa_agent.data.refresh_policy import snapshot_cache_ttl_s
from pa_agent.data.tdx_source import ashare_prefixed_code

logger = logging.getLogger(__name__)

_SUPPORTED_TIMEFRAMES: tuple[str, ...] = (
    "1m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
    "1d",
    "1w",
    "1M",
)

_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
# mkline 分钟线会重定向到 CDN 主机（web3.*），不同网络可达性不同，多主机回退
_MKLINE_HOSTS: tuple[str, ...] = (
    "web.ifzq.gtimg.cn",
    "ifzq.gtimg.cn",
    "web3.ifzq.gtimg.cn",
    "proxy.finance.qq.com",
)
_QUOTE_URL = "https://qt.gtimg.cn/q="

# fqkline 周期参数
_DAY_PERIOD: dict[str, str] = {"1d": "day", "1w": "week", "1M": "month"}
# 响应内 K 线 key：前复权优先，指数等回退原始
_KLINE_KEYS: dict[str, tuple[str, ...]] = {
    "1d": ("qfqday", "day"),
    "1w": ("qfqweek", "week"),
    "1M": ("qfqmonth", "month"),
}
# mkline 周期参数（分钟线；4h 由 60 分钟重采样）
_MINUTE_PERIOD: dict[str, str] = {
    "1m": "m1",
    "5m": "m5",
    "15m": "m15",
    "30m": "m30",
    "1h": "m60",
}

_PRESET_SYMBOLS: tuple[str, ...] = (
    "000001",
    "600519",
    "000300",
    "399006",
)


_COMPACT_TIME_RE = re.compile(r"^\d{8}(?:\d{2}(?:\d{2}(?:\d{2})?)?)?$")


def _normalize_tencent_time(value: Any) -> str:
    """紧凑时间戳（20260827 / 202608271400 / 20260827140000）→ 标准形式。"""
    text = str(value).strip()
    if _COMPACT_TIME_RE.match(text):
        if len(text) == 8:
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        if len(text) == 12:
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}"
        if len(text) == 14:
            return (
                f"{text[0:4]}-{text[4:6]}-{text[6:8]} "
                f"{text[8:10]}:{text[10:12]}:{text[12:14]}"
            )
    return text


def _row_from_tencent(item: list[Any], symbol: str) -> dict[str, Any]:
    """腾讯 K 线行 → 升序 OHLCV dict（成交量由手换算为股/指数原值）。"""
    return {
        "ts_open": row_time_to_ts_ms(_normalize_tencent_time(item[0])),
        "open": float(item[1]),
        "close": float(item[2]),
        "high": float(item[3]),
        "low": float(item[4]),
        "volume": quote_volume_lots_to_shares(float(item[5]), symbol=symbol),
        "amount": 0.0,
        "pct_chg": None,
    }


class TencentSource(DataSource):
    """腾讯财经 A 股行情：纯 HTTP 轮询，无连接维护。"""

    def __init__(self) -> None:
        self._symbol: str = ""
        self._timeframe: str = ""
        self._connected: bool = False
        self._snap_cache_n: int = 0
        self._snap_cache_ts: float = 0.0
        self._snap_cache_bars: list[KlineBar] = []

    def connect(self) -> None:
        self._connected = True
        logger.info("TencentSource connected")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("TencentSource disconnected")

    def list_symbols(self) -> list[str]:
        return list(_PRESET_SYMBOLS)

    def supported_timeframes(self) -> list[str]:
        return list(_SUPPORTED_TIMEFRAMES)

    def subscribe(self, symbol: str, timeframe: str) -> None:
        if timeframe not in _SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"Unsupported timeframe: {timeframe!r}. "
                f"Use one of {list(_SUPPORTED_TIMEFRAMES)}"
            )
        code = normalize_ashare_symbol(symbol)
        if not code:
            raise ValueError("A股代码无效，请输入 6 位数字（如 600519）或指数 sh000300")
        if code != self._symbol or timeframe != self._timeframe:
            self._snap_cache_bars = []
            self._snap_cache_n = 0
        self._symbol = code
        self._timeframe = timeframe
        logger.info("TencentSource subscribed: %s %s", code, timeframe)

    def unsubscribe(self) -> None:
        self._symbol = ""
        self._timeframe = ""
        self._snap_cache_bars = []
        self._snap_cache_n = 0
        logger.info("TencentSource unsubscribed")

    # ── HTTP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _http_get(url: str, *, gbk: bool = False, timeout: float = 12.0) -> str:
        from curl_cffi import requests as cr

        resp = cr.get(url, timeout=timeout, impersonate="chrome")
        if resp.status_code != 200:
            raise DataSourceTransientError(f"腾讯行情 HTTP {resp.status_code}")
        if gbk:
            resp.encoding = "gbk"
        return resp.text

    def _fetch_text(self, url: str, *, gbk: bool = False, attempts: int = 3) -> str:
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                return self._http_get(url, gbk=gbk)
            except DataSourceTransientError:
                raise
            except Exception as exc:  # noqa: BLE001 — 网络抖动重试
                last_exc = exc
                if i + 1 >= attempts:
                    break
                time.sleep(min(1.0, 0.3 + i * 0.3))
        raise DataSourceTransientError(f"腾讯行情请求失败: {last_exc}")

    # ── 快照 ──────────────────────────────────────────────────────────────────

    def latest_snapshot(self, n: int) -> list[KlineBar]:
        if not self._connected:
            raise DataSourceTransientError("腾讯财经数据源未连接")
        if not self._symbol or not self._timeframe:
            raise DataSourceTransientError("腾讯财经未订阅品种/周期")

        now = time.monotonic()
        cache_ttl = snapshot_cache_ttl_s(self._timeframe)
        if (
            self._snap_cache_bars
            and self._snap_cache_n == n
            and now - self._snap_cache_ts < cache_ttl
        ):
            return list(self._snap_cache_bars)

        fetch_n = max(n + 5, 30)
        try:
            rows_asc = self._fetch_history(self._symbol, self._timeframe, fetch_n)
        except DataSourceTransientError:
            raise
        except Exception as exc:
            logger.warning("Tencent fetch failed: %s", exc)
            raise DataSourceTransientError(f"腾讯财经拉取失败: {exc}") from exc

        if not rows_asc:
            raise DataSourceTransientError(
                f"腾讯财经未返回数据: {self._symbol} {self._timeframe}"
            )

        daily = self._timeframe == "1d"
        quote = self._fetch_quote(self._symbol)
        if daily and ashare_trading_day():
            ensure_today_forming_daily_bar(
                rows_asc,
                symbol=self._symbol,
                spot_price=quote["price"] if quote and quote["price"] > 0 else None,
                session_open=quote["open"] if quote else 0.0,
                session_high=quote["high"] if quote else 0.0,
                session_low=quote["low"] if quote else 0.0,
                session_volume_lots=quote["vol"] if quote else 0.0,
                session_amount=quote["amount"] if quote else 0.0,
            )
        if quote is not None and (
            (daily and ashare_trading_day()) or ashare_session_open()
        ):
            self._apply_spot_to_forming(rows_asc, daily=daily, quote=quote)

        rows_newest = list(reversed(rows_asc[-fetch_n:]))
        for i, row in enumerate(rows_newest):
            row["closed"] = not (i == 0 and ashare_head_bar_live(self._timeframe))

        bars = rows_to_kline_bars(rows_newest, n)
        self._snap_cache_n = n
        self._snap_cache_ts = time.monotonic()
        self._snap_cache_bars = list(bars)
        return bars

    # ── 数据获取 ──────────────────────────────────────────────────────────────

    def _fetch_history(self, symbol: str, timeframe: str, n: int) -> list[dict[str, Any]]:
        prefixed = ashare_prefixed_code(symbol)
        if timeframe in ("1d", "1w", "1M"):
            return self._fetch_day(prefixed, timeframe, n)
        if timeframe == "4h":
            rows = self._fetch_minute(prefixed, "1h", n * 4 + 8)
            return resample_rows_to_4h(rows)[-n:]
        return self._fetch_minute(prefixed, timeframe, n)

    def _fetch_day(
        self, prefixed: str, timeframe: str, n: int
    ) -> list[dict[str, Any]]:
        url = f"{_KLINE_URL}?param={prefixed},{_DAY_PERIOD[timeframe]},,,{n + 5},qfq"
        payload = json.loads(self._fetch_text(url))
        data = (payload.get("data") or {}).get(prefixed) or {}
        for key in _KLINE_KEYS[timeframe]:
            arr = data.get(key)
            if isinstance(arr, list) and arr:
                rows = [_row_from_tencent(item, prefixed) for item in arr if item]
                return rows[-(n + 5) :]
        return []

    def _fetch_minute(
        self, prefixed: str, timeframe: str, n: int
    ) -> list[dict[str, Any]]:
        period = _MINUTE_PERIOD[timeframe]
        param = f"param={prefixed},{period},,{n + 8}"
        last_exc: Exception | None = None
        for host in _MKLINE_HOSTS:
            url = f"https://{host}/appstock/app/kline/mkline?{param}"
            try:
                payload = json.loads(self._fetch_text(url))
            except DataSourceTransientError as exc:
                last_exc = exc
                continue
            data = (payload.get("data") or {}).get(prefixed) or {}
            arr = data.get(period)
            if isinstance(arr, list) and arr:
                return [_row_from_tencent(item, prefixed) for item in arr if item][-(n + 8) :]
            last_exc = DataSourceTransientError("腾讯财经分钟线未返回数据")
        raise DataSourceTransientError(f"腾讯财经分钟线拉取失败: {last_exc}")

    # ── 实时报价（刷新形成中 K 线） ─────────────────────────────────────────────

    def _fetch_quote(self, symbol: str) -> dict[str, float] | None:
        prefixed = ashare_prefixed_code(symbol)
        try:
            text = self._fetch_text(_QUOTE_URL + prefixed, gbk=True, attempts=2)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Tencent quote failed: %s", exc)
            return None
        marker = f"v_{prefixed}="
        for line in text.splitlines():
            if marker not in line:
                continue
            try:
                fields = line.split('="', 1)[1].split('"')[0].split("~")
            except (IndexError, ValueError):
                continue
            if len(fields) < 38:
                continue
            try:
                return {
                    "price": float(fields[3]),
                    "prev_close": float(fields[4]),
                    "open": float(fields[5]),
                    "high": float(fields[33]),
                    "low": float(fields[34]),
                    "vol": float(fields[6]),  # 手
                    "amount": float(fields[37]) * 10000.0,  # 万元 → 元
                }
            except (TypeError, ValueError):
                continue
        return None

    def _apply_spot_to_forming(
        self,
        rows_asc: list[dict[str, Any]],
        *,
        daily: bool,
        quote: dict[str, float] | None = None,
    ) -> None:
        if not rows_asc:
            return
        if quote is None:
            quote = self._fetch_quote(self._symbol)
        if quote is None or quote["price"] <= 0:
            return
        apply_session_quote_to_forming_row(
            rows_asc[-1],
            price=quote["price"],
            open_=quote["open"],
            high=quote["high"],
            low=quote["low"],
            volume=quote["vol"],
            amount=quote["amount"],
            prev_close=quote["prev_close"],
            daily=daily,
            volume_lots=True,
            symbol=self._symbol,
        )

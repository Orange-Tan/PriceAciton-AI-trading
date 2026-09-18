"""通达信（TDX）A 股 K 线数据源 —— 基于 pytdx 协议客户端（TCP 直连行情主站）。

与东方财富 / 腾讯财经一样是免费公开行情，无需 token；缺点是依赖第三方
``pytdx`` 库，且行情主站为公开 TCP 服务，个别时段可能不稳定——代码内置了
多台主站并逐个重试。

数据单位约定（与 A 股习惯一致）：
- 个股成交量：TDX 返回的 ``vol`` 已是「股」，无需换算；
- 指数成交量：与 TDX 返回一致，保持原值；
- 实时报价的 ``vol`` 为「手」，刷新形成中 K 线时经 ``volume_lots=True`` 换算。
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from pa_agent.data.ashare_common import (
    apply_session_quote_to_forming_row,
    ashare_head_bar_live,
    ashare_session_open,
    ashare_trading_day,
    ensure_today_forming_daily_bar,
    is_index_symbol,
    normalize_ashare_symbol,
    resample_rows_to_4h,
    row_time_to_ts_ms,
    rows_to_kline_bars,
)
from pa_agent.data.base import DataSource, DataSourceTransientError, KlineBar
from pa_agent.data.refresh_policy import snapshot_cache_ttl_s

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

# pytdx K 线分类：0=5m, 1=15m, 2=30m, 3=1h, 4=1d, 5=周, 6=月, 7=1m
_TF_CATEGORY: dict[str, int] = {
    "1m": 7,
    "5m": 0,
    "15m": 1,
    "30m": 2,
    "1h": 3,
    "1d": 4,
    "1w": 5,
    "1M": 6,
}

# 通达信公开行情主站（从 pytdx 内置主站中挑选实测可用的，覆盖电信/联通/移动）
_TDX_SERVERS: tuple[tuple[str, int], ...] = (
    ("180.153.18.170", 7709),  # 上海电信主站Z1
    ("180.153.18.172", 80),  # 上海电信主站Z80
    ("202.108.253.139", 80),  # 北京联通主站Z80
    ("60.191.117.167", 7709),  # 杭州电信主站J1
    ("115.238.56.198", 7709),  # 杭州电信主站J2
    ("218.75.126.9", 7709),  # 杭州电信主站J3
    ("60.12.136.250", 7709),  # 杭州联通主站J2
    ("59.36.5.11", 7709),  # 安信
    ("117.34.114.13", 7709),  # 国泰君安
)

_CONNECT_TIMEOUT_S = 5.0

_PRESET_SYMBOLS: tuple[str, ...] = (
    "000001",
    "600519",
    "000300",
    "399006",
)


def ashare_prefixed_code(symbol: str) -> str:
    """6 位代码 → 带市场前缀（sh/sz），供通达信与腾讯接口使用。"""
    sym = normalize_ashare_symbol(symbol)
    if sym.startswith(("sh", "sz")):
        return sym
    if is_index_symbol(sym):
        # 000300/000016/000905/000852 → 上证；399xxx → 深证
        if sym.startswith("399"):
            return f"sz{sym}"
        return f"sh{sym}"
    if sym.startswith(("5", "6", "9")):
        return f"sh{sym}"
    return f"sz{sym}"


def _market_for_prefixed(prefixed: str) -> int:
    """通达信市场号：0=深圳，1=上海。"""
    return 1 if prefixed.startswith("sh") else 0


def _tdx_bar_to_row(bar: dict[str, Any], *, volume_scale: float = 1.0) -> dict[str, Any]:
    """TDX bar → 升序 OHLCV dict。

    单位约定：日线/分钟线 ``vol`` 已是「股」（指数为原值），周线/月线 ``vol``
    为「手」，需 ``volume_scale=100`` 换算为股/指数原值（与腾讯日线口径对齐）。
    """
    return {
        "ts_open": row_time_to_ts_ms(bar.get("datetime")),
        "open": float(bar.get("open", 0.0)),
        "high": float(bar.get("high", 0.0)),
        "low": float(bar.get("low", 0.0)),
        "close": float(bar.get("close", 0.0)),
        "volume": float(bar.get("vol", 0.0) or 0.0) * volume_scale,
        "amount": float(bar.get("amount", 0.0) or 0.0),
        "pct_chg": None,
    }


class TdxSource(DataSource):
    """通达信 A 股行情：connect 惰性建连，快照失败后自动切换主站重连。"""

    def __init__(self) -> None:
        self._symbol: str = ""
        self._timeframe: str = ""
        self._connected: bool = False
        self._api: Any = None
        self._api_server: str = ""
        self._snap_cache_n: int = 0
        self._snap_cache_ts: float = 0.0
        self._snap_cache_bars: list[KlineBar] = []

    def connect(self) -> None:
        try:
            import pytdx  # noqa: F401
        except ImportError as exc:
            raise DataSourceTransientError("未安装 pytdx，请执行: pip install pytdx") from exc
        self._connected = True
        logger.info("TdxSource connected")

    def disconnect(self) -> None:
        self._close_api()
        self._connected = False
        logger.info("TdxSource disconnected")

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
        self._ensure_api()
        logger.info("TdxSource subscribed: %s %s", code, timeframe)

    def unsubscribe(self) -> None:
        self._symbol = ""
        self._timeframe = ""
        self._snap_cache_bars = []
        self._snap_cache_n = 0
        self._close_api()
        logger.info("TdxSource unsubscribed")

    # ── 连接管理 ───────────────────────────────────────────────────────────────

    def _close_api(self) -> None:
        api, self._api = self._api, None
        self._api_server = ""
        if api is not None:
            try:
                api.disconnect()
            except Exception as exc:  # noqa: BLE001
                logger.debug("TDX disconnect: %s", exc)

    def _ensure_api(self) -> Any:
        """连接一台可用行情主站；失败抛 DataSourceTransientError。"""
        if self._api is not None:
            return self._api
        from pytdx.hq import TdxHq_API

        servers = list(_TDX_SERVERS)
        start = random.randrange(len(servers)) if len(servers) > 1 else 0
        last_exc: Exception | None = None
        for i in range(len(servers)):
            ip, port = servers[(start + i) % len(servers)]
            api = TdxHq_API(heartbeat=True, auto_retry=True)
            try:
                if api.connect(ip, port, time_out=_CONNECT_TIMEOUT_S):
                    self._api = api
                    self._api_server = f"{ip}:{port}"
                    logger.info("TdxSource connected to %s", self._api_server)
                    return api
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                try:
                    api.disconnect()
                except Exception:  # noqa: BLE001
                    pass
            else:
                try:
                    api.disconnect()
                except Exception:  # noqa: BLE001
                    pass
        raise DataSourceTransientError(
            f"无法连接通达信行情服务器（已尝试 {len(servers)} 台）: {last_exc}"
        )

    def _call_tdx(self, fn: Any) -> Any:
        """执行一次 TDX 请求；返回 None 视为请求失败（连接可能已断开）。"""
        result = fn()
        if result is None:
            raise DataSourceTransientError("通达信行情请求失败（连接可能已断开）")
        return result

    # ── 快照 ──────────────────────────────────────────────────────────────────

    def latest_snapshot(self, n: int) -> list[KlineBar]:
        if not self._connected:
            raise DataSourceTransientError("通达信数据源未连接")
        if not self._symbol or not self._timeframe:
            raise DataSourceTransientError("通达信未订阅品种/周期")
        self._ensure_api()

        now = time.monotonic()
        cache_ttl = snapshot_cache_ttl_s(self._timeframe)
        if (
            self._snap_cache_bars
            and self._snap_cache_n == n
            and now - self._snap_cache_ts < cache_ttl
        ):
            return list(self._snap_cache_bars)

        fetch_n = max(n + 5, 60)
        try:
            rows_asc = self._fetch_history(self._symbol, self._timeframe, fetch_n)
        except DataSourceTransientError:
            self._close_api()  # 下一次快照自动换主站重连
            raise
        except Exception as exc:
            self._close_api()
            raise DataSourceTransientError(f"通达信拉取失败: {exc}") from exc

        if not rows_asc:
            raise DataSourceTransientError(f"通达信未返回数据: {self._symbol} {self._timeframe}")

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
        if quote is not None and ((daily and ashare_trading_day()) or ashare_session_open()):
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
        market = _market_for_prefixed(prefixed)
        code6 = prefixed[2:]
        if timeframe == "4h":
            rows = self._fetch_minute(market, code6, "1h", n * 4 + 8)
            return resample_rows_to_4h(rows)[-n:]
        if timeframe in ("1m", "5m", "15m", "30m", "1h"):
            return self._fetch_minute(market, code6, timeframe, n)
        return self._fetch_daily(market, code6, timeframe, n)

    def _fetch_daily(self, market: int, code6: str, timeframe: str, n: int) -> list[dict[str, Any]]:
        category = _TF_CATEGORY[timeframe]
        api = self._ensure_api()
        if is_index_symbol(code6):
            bars = self._call_tdx(lambda: api.get_index_bars(category, market, code6, 0, n + 5))
        else:
            bars = self._call_tdx(lambda: api.get_security_bars(category, market, code6, 0, n + 5))
        if not bars:
            return []
        # 周线/月线返回的 vol 是「手」，×100 换算为股/指数原值
        scale = 100.0 if timeframe in ("1w", "1M") else 1.0
        return [_tdx_bar_to_row(b, volume_scale=scale) for b in bars][-(n + 5) :]

    def _fetch_minute(
        self, market: int, code6: str, timeframe: str, n: int
    ) -> list[dict[str, Any]]:
        category = _TF_CATEGORY[timeframe]
        api = self._ensure_api()
        if is_index_symbol(code6):
            bars = self._call_tdx(lambda: api.get_index_bars(category, market, code6, 0, n + 8))
        else:
            bars = self._call_tdx(lambda: api.get_security_bars(category, market, code6, 0, n + 8))
        if not bars:
            return []
        return [_tdx_bar_to_row(b) for b in bars][-(n + 8) :]

    # ── 实时报价（刷新形成中 K 线） ─────────────────────────────────────────────

    def _fetch_quote(self, symbol: str) -> dict[str, float] | None:
        try:
            prefixed = ashare_prefixed_code(symbol)
            market = _market_for_prefixed(prefixed)
            quotes = self._call_tdx(lambda: self._api.get_security_quotes([(market, prefixed[2:])]))
        except Exception as exc:  # noqa: BLE001
            logger.debug("TDX quote failed: %s", exc)
            return None
        if not quotes:
            return None
        q = quotes[0]
        try:
            return {
                "price": float(q.get("price") or 0.0),
                "open": float(q.get("open") or 0.0),
                "high": float(q.get("high") or 0.0),
                "low": float(q.get("low") or 0.0),
                "prev_close": float(q.get("last_close") or 0.0),
                "vol": float(q.get("vol") or 0.0),  # 手
                "amount": float(q.get("amount") or 0.0),  # 元
            }
        except (TypeError, ValueError):
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

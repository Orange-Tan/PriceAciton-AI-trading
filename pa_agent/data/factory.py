"""Construct :class:`DataSource` implementations by kind id."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Literal

from pa_agent.data.base import DataSource
from pa_agent.data.market_defaults import (
    A_SHARE_DEFAULT_SYMBOL,
    A_SHARE_SOURCE_KINDS,
    GOLD_TV_SYMBOL,
)

#: 连通性探测使用周期：所有数据源均支持日线，且拉取最快。
_PROBE_TIMEFRAME = "1d"
_PROBE_BARS = 3
#: 单个来源探测超时（秒）。
_PROBE_TIMEOUT_S = 25.0
#: 自选股点选 A 股时后台探测国内来源的单个来源超时（秒）。
_WATCHLIST_PROBE_TIMEOUT_S = 8.0

DataSourceKind = Literal[
    "tradingview",
    "akshare",
    "eastmoney",
    "tushare",
    "tdx",
    "tencent",
]

# All switchable data sources, shown in the toolbar combo and settings dialog.
# ``eastmoney`` is built-in HTTP (no token); ``tushare`` needs a token.
DATA_SOURCE_CHOICES: tuple[tuple[DataSourceKind, str], ...] = (
    ("tradingview", "TradingView"),
    ("akshare", "AkShare（A股）"),
    ("eastmoney", "东方财富（A股）"),
    ("tushare", "Tushare（A股）"),
    ("tdx", "通达信（A股）"),
    ("tencent", "腾讯财经（A股）"),
)

# Reserved for programmatic-only kinds; currently empty because every kind is
# user-switchable via DATA_SOURCE_CHOICES.
_HIDDEN_KINDS: frozenset[DataSourceKind] = frozenset()

_DEFAULT_SYMBOLS: dict[DataSourceKind, str] = {
    "tradingview": GOLD_TV_SYMBOL,
    "akshare": A_SHARE_DEFAULT_SYMBOL,
    "eastmoney": A_SHARE_DEFAULT_SYMBOL,
    "tushare": A_SHARE_DEFAULT_SYMBOL,
    "tdx": A_SHARE_DEFAULT_SYMBOL,
    "tencent": A_SHARE_DEFAULT_SYMBOL,
}


def default_tradingview_exchange() -> str:
    """Empty string = UI «（自动）» — probe all TV preset venues."""
    return ""


def normalize_data_source_kind(kind: str | None) -> DataSourceKind:
    """Return a supported data-source kind, defaulting to TradingView."""
    supported = {k for k, _ in DATA_SOURCE_CHOICES} | _HIDDEN_KINDS
    if kind in supported:
        return kind  # type: ignore[return-value]
    return "tradingview"


def data_source_label(kind: str | None) -> str:
    """Human-readable label for *kind*."""
    normalized = normalize_data_source_kind(kind)
    for key, label in DATA_SOURCE_CHOICES:
        if key == normalized:
            return label
    return "TradingView"


def default_symbol_for_kind(kind: str | None) -> str:
    return _DEFAULT_SYMBOLS[normalize_data_source_kind(kind)]


def create_data_source(kind: str | None) -> DataSource:
    """Instantiate a fresh data source for *kind* (not connected)."""
    normalized = normalize_data_source_kind(kind)
    if normalized == "tradingview":
        from pa_agent.data.tradingview import TradingViewSource

        return TradingViewSource()
    if normalized == "eastmoney":
        from pa_agent.data.eastmoney_source import EastMoneySource

        return EastMoneySource()
    if normalized == "tushare":
        from pa_agent.config.paths import SETTINGS_JSON_PATH
        from pa_agent.config.settings import load_settings
        from pa_agent.data.tushare_source import TushareSource

        return TushareSource(settings=load_settings(SETTINGS_JSON_PATH))
    if normalized == "akshare":
        from pa_agent.data.akshare_source import AkShareSource

        return AkShareSource()
    if normalized == "tdx":
        from pa_agent.data.tdx_source import TdxSource

        return TdxSource()
    if normalized == "tencent":
        from pa_agent.data.tencent_source import TencentSource

        return TencentSource()
    raise ValueError(f"未知数据源: {kind!r}")


def probe_data_source(
    kind: str | None, timeout_s: float = _PROBE_TIMEOUT_S
) -> tuple[bool, str]:
    """探测 *kind* 数据源连通性，返回 ``(是否连通, 说明)``。

    在全新实例上执行 ``connect()`` + 拉取少量日线，失败不抛异常，统一转为
    ``(False, 说明)``。探测在独立线程中执行并受 *timeout_s* 超时约束；
    超时返回后，卡住的探测线程仍会在其自身返回时自行退出。
    """
    normalized = normalize_data_source_kind(kind)
    symbol = default_symbol_for_kind(normalized)

    def _probe() -> int:
        source = create_data_source(normalized)
        source.connect()
        source.subscribe(symbol, _PROBE_TIMEFRAME)
        bars = source.latest_snapshot(_PROBE_BARS)
        return len(bars) if bars else 0

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ds-probe")
    try:
        future = executor.submit(_probe)
        count = future.result(timeout=timeout_s)
    except FutureTimeoutError:
        future.cancel()
        return False, f"检测超时（> {timeout_s:.0f}s），请检查网络后重试"
    except Exception as exc:  # noqa: BLE001 — 连通失败即结果
        detail = str(exc).strip() or type(exc).__name__
        if len(detail) > 120:
            detail = detail[:117] + "…"
        return False, detail
    finally:
        executor.shutdown(wait=False, cancel_futures=True)  # 后台线程完成探测后自行退出
    if count > 0:
        return True, f"连通正常：{symbol} {_PROBE_TIMEFRAME} 已返回 {count} 根K线"
    return False, "连接成功但未返回K线数据"


# ── 国内 A 股来源连通缓存（供自选股点选自动选源）──────────────────────────────
# 与设置面板的探测结果共用同一份进程内缓存，避免点选自选股时重复慢探测。
_DOMESTIC_PROBE_CACHE: dict[str, tuple[float, bool, str]] = {}
_DOMESTIC_PROBE_TTL_S = 30 * 60


def cached_domestic_source_status(
    ttl_s: float = _DOMESTIC_PROBE_TTL_S,
) -> dict[str, tuple[bool, str]]:
    """仅读缓存：返回各国内来源最近一次连通探测结果（未过 TTL 才有效）。"""
    now = time.monotonic()
    out: dict[str, tuple[bool, str]] = {}
    for kind in A_SHARE_SOURCE_KINDS:
        hit = _DOMESTIC_PROBE_CACHE.get(kind)
        if hit is not None and now - hit[0] < ttl_s:
            out[kind] = (hit[1], hit[2])
    return out


def probed_a_share_source_status(
    timeout_s: float = _WATCHLIST_PROBE_TIMEOUT_S,
    ttl_s: float = _DOMESTIC_PROBE_TTL_S,
) -> dict[str, tuple[bool, str]]:
    """并行探测（或复用缓存）国内所有 A 股来源，返回 ``kind -> (ok, detail)``。

    缓存命中直接复用；未命中/过期者并行探测，总耗时 ≈ 单来源超时而非累加。
    """
    now = time.monotonic()
    results: dict[str, tuple[bool, str]] = {}
    stale: list[str] = []
    for kind in A_SHARE_SOURCE_KINDS:
        hit = _DOMESTIC_PROBE_CACHE.get(kind)
        if hit is not None and now - hit[0] < ttl_s:
            results[kind] = (hit[1], hit[2])
        else:
            stale.append(kind)
    if stale:
        with ThreadPoolExecutor(
            max_workers=min(len(stale), 5), thread_name_prefix="ds-probe-batch"
        ) as pool:
            futures = {pool.submit(probe_data_source, kind, timeout_s): kind for kind in stale}
            for future in futures:
                kind = futures[future]
                try:
                    results[kind] = future.result()
                except Exception as exc:  # noqa: BLE001 — 探测失败即结果
                    results[kind] = (False, str(exc))
        for kind in stale:
            ok, detail = results.get(kind, (False, ""))
            _DOMESTIC_PROBE_CACHE[kind] = (now, ok, detail)
    return results


def first_connected_a_share_source(
    timeout_s: float = _WATCHLIST_PROBE_TIMEOUT_S,
    ttl_s: float = _DOMESTIC_PROBE_TTL_S,
) -> str | None:
    """按 :data:`A_SHARE_SOURCE_KINDS` 优先级返回第一个连通成功的国内来源，失败返回 None。"""
    status = probed_a_share_source_status(timeout_s=timeout_s, ttl_s=ttl_s)
    for kind in A_SHARE_SOURCE_KINDS:
        ok, _detail = status.get(kind, (False, ""))
        if ok:
            return kind
    return None

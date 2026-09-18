"""Qt-free normalization helpers for grouped watchlist settings."""

from __future__ import annotations

from collections.abc import Mapping

DEFAULT_GROUP = "全部"
DEFAULT_WATCHLIST_GROUPS: dict[str, list[str]] = {
    DEFAULT_GROUP: ["sh000001", "sz399001", "sz399006"],
    "持仓": [],
    "美股": [],
    "港股": [],
}


def _symbols(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = str(raw or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def normalize_watchlist_groups(value: object) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {DEFAULT_GROUP: []}
    if not isinstance(value, Mapping):
        return result
    for raw_name, raw_symbols in value.items():
        name = str(raw_name or "").strip()
        if not name:
            continue
        symbols = _symbols(raw_symbols)
        if name == DEFAULT_GROUP:
            result[DEFAULT_GROUP] = symbols
        elif name not in result:
            result[name] = symbols
    return result


def default_watchlist_groups() -> dict[str, list[str]]:
    """Return a fresh copy of the first-run watchlist sections and indices."""
    return {name: list(symbols) for name, symbols in DEFAULT_WATCHLIST_GROUPS.items()}


def migrate_watchlist(groups: object, legacy_symbols: object) -> dict[str, list[str]]:
    legacy = _symbols(legacy_symbols)
    if not isinstance(groups, Mapping) and not legacy:
        return default_watchlist_groups()
    if isinstance(groups, Mapping) and not legacy:
        named = {str(name or "").strip() for name in groups if str(name or "").strip()}
        if named in ({DEFAULT_GROUP}, set()) and not _symbols(groups.get(DEFAULT_GROUP)):
            return default_watchlist_groups()
    normalized = normalize_watchlist_groups(groups)
    has_explicit = isinstance(groups, Mapping) and any(str(name or "").strip() for name in groups)
    if not has_explicit:
        normalized[DEFAULT_GROUP] = legacy
    return normalized


def serialize_watchlist_groups(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    return {name: list(symbols) for name, symbols in normalize_watchlist_groups(groups).items()}

"""Pure tests for grouped watchlist normalization and legacy migration."""
from __future__ import annotations

from pa_agent.config.watchlist_store import (
    DEFAULT_GROUP,
    migrate_watchlist,
    normalize_watchlist_groups,
    serialize_watchlist_groups,
)


def test_normalize_groups_keeps_all_first_and_deduplicates():
    value = {
        "观察列表": [" 000001 ", "000001", "XAUUSD"],
        "全部": ["600519", "600519"],
        "": ["ignored"],
    }
    assert normalize_watchlist_groups(value) == {
        DEFAULT_GROUP: ["600519"],
        "观察列表": ["000001", "XAUUSD"],
    }


def test_migrate_legacy_watchlist_when_groups_missing():
    assert migrate_watchlist(None, ["600519", "000001", "600519"]) == {
        DEFAULT_GROUP: ["600519", "000001"]
    }


def test_explicit_groups_take_precedence_over_legacy_values():
    groups = {"核心持仓": ["600519"], DEFAULT_GROUP: ["000001"]}
    assert migrate_watchlist(groups, ["XAUUSD"]) == {
        DEFAULT_GROUP: ["000001"],
        "核心持仓": ["600519"],
    }


def test_serialize_returns_json_safe_copy():
    source = {DEFAULT_GROUP: ["600519"], "观察": ["000001"]}
    result = serialize_watchlist_groups(source)
    assert result == source
    assert result is not source
    result[DEFAULT_GROUP].append("XAUUSD")
    assert source[DEFAULT_GROUP] == ["600519"]

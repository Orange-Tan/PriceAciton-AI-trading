"""Compatibility re-export for the Qt-free watchlist store."""

from pa_agent.config.watchlist_store import (
    DEFAULT_GROUP,
    migrate_watchlist,
    normalize_watchlist_groups,
    serialize_watchlist_groups,
)

__all__ = [
    "DEFAULT_GROUP",
    "migrate_watchlist",
    "normalize_watchlist_groups",
    "serialize_watchlist_groups",
]

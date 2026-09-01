from __future__ import annotations

from pa_agent.notify.feishu_notifier import _TokenCache


def test_token_cache_refreshes_when_app_credentials_change(monkeypatch) -> None:
    cache = _TokenCache()
    calls: list[tuple[str, str]] = []

    def refresh(app_id: str, app_secret: str) -> str:
        calls.append((app_id, app_secret))
        cache._token = f"token-{app_id}"
        cache._credentials = (app_id, app_secret)
        cache._expire_at = 10**12
        return cache._token

    monkeypatch.setattr(cache, "_refresh", refresh)
    assert cache.get("app-a", "secret-a") == "token-app-a"
    assert cache.get("app-a", "secret-a") == "token-app-a"
    assert cache.get("app-b", "secret-b") == "token-app-b"
    assert calls == [("app-a", "secret-a"), ("app-b", "secret-b")]

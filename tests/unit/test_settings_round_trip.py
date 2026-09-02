"""Unit tests for settings load/save round-trip (task 2.4)."""
from __future__ import annotations
import json
import sys
import types
from unittest.mock import patch

import pytest
from pathlib import Path
from pa_agent.config.settings import AIProviderSettings, Settings, load_settings, save_settings


@pytest.fixture(autouse=True)
def _reset_keyring_cache(monkeypatch):
    monkeypatch.setattr("pa_agent.config.settings._keyring_cached_value", None)
    monkeypatch.setattr("pa_agent.config.settings._keyring_route_cached_values", {})


def test_defaults(tmp_path):
    """load_settings on a missing file returns defaults and creates the file."""
    p = tmp_path / "settings.json"
    s = load_settings(p)
    assert s.provider.model == "deepseek-v4-flash"
    assert s.provider.base_url == "https://api.deepseek.com"
    assert s.provider.thinking is True
    assert s.provider.reasoning_effort == "high"
    assert s.provider.context_window == 2_000_000
    assert s.general.analysis_bar_count == 100
    assert s.general.last_symbol == "XAUUSD"
    assert s.general.last_timeframe == "15m"
    assert s.general.decision_stance == "balanced"
    assert s.general.decision_flow_auto_play is True
    assert s.general.auto_resume_chart_after_analysis is False
    assert p.exists(), "defaults should be written to disk"


def test_round_trip(tmp_path, monkeypatch):
    """save → load preserves all fields."""
    stored: dict[tuple[str, str], str] = {}
    monkeypatch.setitem(
        sys.modules,
        "keyring",
        types.SimpleNamespace(
            set_password=lambda service, username, value: stored.__setitem__((service, username), value),
            get_password=lambda service, username: stored.get((service, username)),
            delete_password=lambda service, username: stored.pop((service, username), None),
        ),
    )
    p = tmp_path / "settings.json"
    original = Settings()
    original.provider.api_key = "sk-test-1234"
    original.general.last_symbol = "BTCUSDT"
    save_settings(original, p)
    loaded = load_settings(p)
    assert loaded.provider.api_key == "sk-test-1234"
    # Crypto symbols migrate to gold defaults on load
    assert loaded.general.last_symbol == "XAUUSD"
    assert loaded.provider.model == original.provider.model


def test_api_key_is_stored_in_keyring_not_on_disk(tmp_path, monkeypatch):
    """The saved JSON omits the API key and delegates storage to keyring."""
    stored: dict[tuple[str, str], str] = {}
    fake_keyring = types.SimpleNamespace(
        set_password=lambda service, username, value: stored.__setitem__((service, username), value),
        get_password=lambda service, username: stored.get((service, username)),
        delete_password=lambda service, username: stored.pop((service, username), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    p = tmp_path / "settings.json"
    s = Settings()
    s.provider.api_key = "sk-super-secret-key"
    save_settings(s, p)
    raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["provider"]["api_key"] == ""
    assert "sk-super-secret-key" not in raw
    loaded = load_settings(p)
    assert loaded.provider.api_key == "sk-super-secret-key"


def test_feishu_secrets_are_not_written_to_disk(tmp_path, monkeypatch):
    """Feishu app credentials stay in memory and are redacted from JSON."""
    monkeypatch.setitem(
        sys.modules,
        "keyring",
        types.SimpleNamespace(set_password=lambda *_args: None, get_password=lambda *_args: None),
    )
    p = tmp_path / "settings.json"
    s = Settings()
    s.feishu.app_secret = "feishu-secret"
    s.feishu.secret = "signing-secret"
    save_settings(s, p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["feishu"]["app_secret"] == ""
    assert data["feishu"]["secret"] == ""


def test_repeated_settings_saves_do_not_rewrite_same_key(tmp_path, monkeypatch):
    calls: list[str] = []
    fake_keyring = types.SimpleNamespace(
        set_password=lambda service, username, value: calls.append(value),
        get_password=lambda service, username: None,
        delete_password=lambda service, username: None,
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    p = tmp_path / "settings.json"
    s = Settings()
    s.provider.api_key = "sk-repeat"
    save_settings(s, p)
    save_settings(s, p)
    assert calls == ["sk-repeat"]


def test_saving_default_settings_does_not_touch_keyring(tmp_path, monkeypatch):
    calls: list[str] = []
    fake_keyring = types.SimpleNamespace(
        set_password=lambda service, username, value: calls.append(f"set:{value}"),
        get_password=lambda service, username: calls.append("get") or None,
        delete_password=lambda service, username: calls.append("delete"),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    save_settings(Settings(), tmp_path / "settings.json")
    assert calls == []


def test_clearing_api_key_removes_existing_keyring_entry(tmp_path, monkeypatch):
    calls: list[str] = []
    fake_keyring = types.SimpleNamespace(
        set_password=lambda service, username, value: calls.append(f"set:{value}"),
        get_password=lambda service, username: "old-key",
        delete_password=lambda service, username: calls.append("delete"),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    p = tmp_path / "settings.json"
    from pa_agent.config.settings import _keyring_get

    _keyring_get()  # Prime the in-process cache from the existing keyring value.
    save_settings(Settings(), p)
    assert calls == ["delete"]


def test_route_credentials_do_not_overwrite_default_provider_key(tmp_path, monkeypatch):
    """Gateway route tokens must use a separate keyring item from normal API keys."""
    stored: dict[tuple[str, str], str] = {}
    fake_keyring = types.SimpleNamespace(
        set_password=lambda service, username, value: stored.__setitem__((service, username), value),
        get_password=lambda service, username: stored.get((service, username)),
        delete_password=lambda service, username: stored.pop((service, username), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setattr("pa_agent.config.settings._keyring_cached_value", None)

    p = tmp_path / "settings.json"
    normal = Settings()
    normal.provider.api_key = "sk-normal"
    save_settings(normal, p)

    gateway = Settings()
    gateway.provider = AIProviderSettings(
        model="openclaw",
        base_url="http://127.0.0.1:51187/v1",
        api_key="qclaw-token",
    )
    save_settings(gateway, p)

    assert stored[("pa-agent", "provider_api_key")] == "sk-normal"
    assert stored[("pa-agent", "provider_api_key:qclaw")] == "qclaw-token"

    loaded = load_settings(p)
    assert loaded.provider.api_key == "qclaw-token"

    p.write_text(json.dumps({"provider": {"model": "deepseek-v4-flash"}}), encoding="utf-8")
    loaded_normal = load_settings(p)
    assert loaded_normal.provider.api_key == "sk-normal"


def test_corrupt_json_returns_defaults(tmp_path):
    """Corrupt settings.json falls back to defaults without raising."""
    p = tmp_path / "settings.json"
    p.write_text("{not valid json", encoding="utf-8")
    s = load_settings(p)
    assert s.provider.model == "deepseek-v4-flash"


@pytest.mark.parametrize("raw", [None, [], {"general": None}, {"provider": []}])
def test_invalid_settings_shape_returns_defaults(tmp_path, raw):
    """Valid JSON with an invalid object shape must not crash startup."""
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    loaded = load_settings(p)
    assert isinstance(loaded, Settings)


def test_missing_api_key_leaves_api_key_blank(tmp_path, monkeypatch):
    """If api_key is absent, api_key stays empty string."""
    p = tmp_path / "settings.json"
    data = Settings().model_dump()
    data["provider"].pop("api_key", None)
    data["provider"].pop("api_key_encrypted", None)
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setitem(
        sys.modules,
        "keyring",
        types.SimpleNamespace(get_password=lambda service, username: None),
    )
    s = load_settings(p)
    assert s.provider.api_key == ""


def test_feishu_round_trip(tmp_path):
    """save → load preserves feishu settings."""
    p = tmp_path / "settings.json"
    original = Settings()
    original.feishu.webhook_url = "https://example.com/hook"
    original.feishu.secret = "sec"
    original.feishu.app_id = "cli_test"
    save_settings(original, p)
    loaded = load_settings(p)
    assert loaded.feishu.webhook_url == "https://example.com/hook"
    assert loaded.feishu.secret == "sec"
    assert loaded.feishu.app_id == "cli_test"


def test_pushplus_round_trip(tmp_path):
    """save → load preserves pushplus settings."""
    p = tmp_path / "settings.json"
    original = Settings()
    original.pushplus.token = "pp-test-token"
    original.pushplus.enabled = False
    save_settings(original, p)
    loaded = load_settings(p)
    assert loaded.pushplus.token == "pp-test-token"
    assert loaded.pushplus.enabled is False


def test_tushare_round_trip(tmp_path):
    """save → load preserves tushare token."""
    p = tmp_path / "settings.json"
    original = Settings()
    original.tushare.token = "ts-test-token"
    save_settings(original, p)
    loaded = load_settings(p)
    assert loaded.tushare.token == "ts-test-token"


def test_pushplus_auto_disabled_when_enabled_without_token(tmp_path):
    """load_settings disables pushplus when enabled but token empty."""
    p = tmp_path / "settings.json"
    p.write_text(
        '{"pushplus": {"enabled": true, "token": ""}}',
        encoding="utf-8",
    )
    with patch.dict("os.environ", {}, clear=True):
        loaded = load_settings(p)
    assert loaded.pushplus.enabled is False
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved["pushplus"]["enabled"] is False


def test_migrate_legacy_feishu_json(tmp_path):
    """Legacy config/feishu.json is merged into settings.json on load."""
    p = tmp_path / "settings.json"
    legacy = tmp_path / "feishu.json"
    save_settings(Settings(), p)
    legacy.write_text(
        json.dumps(
            {
                "enabled": True,
                "webhook_url": "https://example.com/legacy-hook",
                "secret": "legacy-secret",
                "app_id": "cli_legacy",
                "app_secret": "legacy-app-secret",
                "notify_on_order_only": True,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_settings(p)
    assert loaded.feishu.webhook_url == "https://example.com/legacy-hook"
    assert loaded.feishu.secret == "legacy-secret"
    assert loaded.feishu.app_id == "cli_legacy"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["feishu"]["webhook_url"] == "https://example.com/legacy-hook"

"""Tests for the left-side watchlist (自选股) panel and its MainWindow wiring."""

from __future__ import annotations

import time
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6")


class _Combo:
    def __init__(self, value: str) -> None:
        self.value = value

    def currentText(self) -> str:
        return self.value

    def blockSignals(self, _blocked: bool) -> None:
        pass

    def setCurrentText(self, value: str) -> None:
        self.value = value

    def findData(self, _value: str) -> int:
        return -1

    def setCurrentIndex(self, _index: int) -> None:
        pass


@pytest.fixture(autouse=True)
def _clean_probe_cache():
    import pa_agent.data.factory as factory_mod

    old = dict(factory_mod._DOMESTIC_PROBE_CACHE)
    factory_mod._DOMESTIC_PROBE_CACHE.clear()
    yield
    factory_mod._DOMESTIC_PROBE_CACHE.clear()
    factory_mod._DOMESTIC_PROBE_CACHE.update(old)


def _seed_cache(ok_kinds: tuple[str, ...]) -> None:
    import pa_agent.data.factory as factory_mod

    now = time.monotonic()
    for kind in factory_mod.A_SHARE_SOURCE_KINDS:
        factory_mod._DOMESTIC_PROBE_CACHE[kind] = (
            now,
            kind in ok_kinds,
            "ok" if kind in ok_kinds else "not reachable",
        )


def _make_window(**attrs):
    from pa_agent.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window._switching = False
    window._demo_mode = False
    window._active_data_source_kind = "tradingview"
    window._ctx = SimpleNamespace(data_source=SimpleNamespace(_connected=True), settings=None)
    window._status_bar = SimpleNamespace(showMessage=lambda _msg: None)
    window._symbol_combo = _Combo("XAUUSD")
    window._tf_combo = _Combo("15m")
    for key, value in attrs.items():
        setattr(window, key, value)
    return window


# ── Settings field ────────────────────────────────────────────────────────────


def test_watchlist_settings_default_and_round_trip() -> None:
    from pa_agent.config.settings import GeneralSettings

    s = GeneralSettings()
    assert s.watchlist == ["sh000001", "sz399001", "sz399006"]

    s.watchlist = ["600519", "000001", "XAUUSD"]
    data = s.model_dump()
    assert data["watchlist"] == ["600519", "000001", "XAUUSD"]

    loaded = GeneralSettings.model_validate({"watchlist": data["watchlist"]})
    assert loaded.watchlist == ["600519", "000001", "XAUUSD"]


def test_watchlist_settings_validator_dedupes_and_strips() -> None:
    from pa_agent.config.settings import GeneralSettings

    s = GeneralSettings.model_validate(
        {
            "watchlist": [
                " 600519 ",
                "600519",
                "",
                None,
                "000001",
                "sh000300",
                "000001",
            ]
        }
    )
    assert s.watchlist == ["600519", "000001", "sh000300"]


def test_watchlist_settings_accepts_string() -> None:
    from pa_agent.config.settings import GeneralSettings

    s = GeneralSettings.model_validate({"watchlist": "600519"})
    assert s.watchlist == ["600519"]


def test_watchlist_settings_migrates_groups_and_legacy_watchlist() -> None:
    from pa_agent.config.settings import GeneralSettings

    migrated = GeneralSettings.model_validate({"watchlist": ["600519", "000001"]})
    assert migrated.watchlist_groups == {"全部": ["600519", "000001"]}
    explicit = GeneralSettings.model_validate(
        {"watchlist": ["XAUUSD"], "watchlist_groups": {"观察": ["000001"]}}
    )
    assert explicit.watchlist_groups == {"全部": [], "观察": ["000001"]}


def test_default_watchlist_groups_include_market_sections_and_indices() -> None:
    from pa_agent.config.settings import GeneralSettings

    settings = GeneralSettings()
    assert list(settings.watchlist_groups) == ["全部", "持仓", "美股", "港股"]
    assert settings.watchlist_groups["全部"] == ["sh000001", "sz399001", "sz399006"]
    assert settings.watchlist == ["sh000001", "sz399001", "sz399006"]


def test_empty_legacy_group_is_seeded_with_default_sections() -> None:
    from pa_agent.config.watchlist_store import migrate_watchlist

    assert migrate_watchlist({"全部": []}, []) == {
        "全部": ["sh000001", "sz399001", "sz399006"],
        "持仓": [],
        "美股": [],
        "港股": [],
    }


# ── WatchlistPanel widget ─────────────────────────────────────────────────────


def test_group_column_width_fits_longest_group_name(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    names = ["港股", "科技成长", "高股息红利"]
    panel = WatchlistPanel({name: [] for name in names})
    qtbot.addWidget(panel)

    expected = panel._group_column_width_for(names)
    assert panel._group_splitter.sizes()[0] == expected
    assert panel._group_column.maximumWidth() > expected


def test_watchlist_uses_compact_group_and_stock_headers(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"港股": []})
    qtbot.addWidget(panel)

    assert panel._group_header.text() == "板块"
    assert panel._stock_header.text() == "自选股"
    assert panel._add_group_btn.text() == "+"
    assert panel._add_symbol_btn.text() == "+"


def test_add_actions_remain_visible_and_fixed_in_narrow_columns(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"港股": []})
    qtbot.addWidget(panel)
    panel.resize(220, 260)
    panel.show()
    qtbot.waitExposed(panel)

    assert panel._add_group_btn.isVisible()
    assert panel._add_symbol_btn.isVisible()
    assert panel._add_group_btn.width() == 28
    assert panel._add_symbol_btn.width() == 28
    assert panel._add_group_btn.y() <= panel._group_header.height()
    assert panel._add_symbol_btn.y() <= panel._stock_header.height()


def test_watchlist_table_stretches_to_bottom_for_scrollbar(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"港股": ["0700", "9988", "1810"]})
    qtbot.addWidget(panel)
    panel.resize(320, 360)
    panel.show()
    qtbot.waitExposed(panel)

    assert panel._table.geometry().bottom() >= panel._stock_column.height() - 36


def test_group_column_content_is_pinned_to_top(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"全部": [], "持仓": [], "美股": [], "港股": []})
    qtbot.addWidget(panel)
    panel.resize(320, 520)
    panel.show()
    qtbot.waitExposed(panel)

    assert panel._group_header.y() <= 4
    assert panel._group_list.y() <= panel._group_header.height() + 4


def test_watchlist_panel_add_dedup_and_symbols(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel()
    qtbot.addWidget(panel)
    assert panel.add_symbol("600519") is True


def test_name_lookup_failure_is_backed_off(qtbot, monkeypatch) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel(["600519"])
    qtbot.addWidget(panel)
    starts = []
    monkeypatch.setattr(panel._name_lookup_pool, "start", lambda task: starts.append(task))
    panel._name_lookup_failures.clear()
    monkeypatch.setattr("pa_agent.gui.watchlist_panel.time.monotonic", lambda: 100.0)
    panel._request_name_lookup("600519")
    panel._name_lookup_pending.clear()
    panel._on_name_resolved("600519", "")
    panel._request_name_lookup("600519")
    assert len(starts) == 1
    assert panel.add_symbol("600519") is False  # dup rejected
    assert panel.add_symbol("000001") is True
    assert panel.symbols() == ["600519", "000001"]


def test_watchlist_panel_normalizes_ashare_inputs(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel()
    qtbot.addWidget(panel)
    panel.add_symbol("sh600519")
    panel.add_symbol("sh000300")
    panel.add_symbol("XAUUSD")
    panel.add_symbol("小米集团")
    assert panel.symbols() == ["600519", "sh000300", "XAUUSD", "小米集团"]


def test_watchlist_panel_remove_selected(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel(["600519", "000001"])
    qtbot.addWidget(panel)
    panel._list.setCurrentRow(0)
    panel.remove_selected()
    assert panel.symbols() == ["000001"]
    panel.remove_selected()
    assert panel.symbols() == []


def test_watchlist_panel_symbol_selected_signal(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel(["600519"])
    qtbot.addWidget(panel)
    emitted: list[str] = []
    panel.symbol_selected.connect(emitted.append)
    item = panel._list.item(0)
    assert item is not None
    panel._on_item_clicked(item)
    assert emitted == ["600519"]


def test_watchlist_panel_list_changed_signal(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel()
    qtbot.addWidget(panel)
    changed: list[int] = []
    panel.list_changed.connect(lambda: changed.append(1))
    panel.add_symbol("600519")
    panel.add_symbol("600519")  # dup — no emission
    panel.remove_selected()  # nothing selected — no emission
    assert len(changed) == 1


def test_watchlist_panel_groups_and_quote_table(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"全部": ["600519"]})
    qtbot.addWidget(panel)
    assert panel.groups() == {"全部": ["600519"]}
    assert panel.current_group() == "全部"
    assert panel.add_group("核心持仓") is True
    assert panel.add_symbol("600519", group="核心持仓") is True
    assert panel.add_symbol("600519", group="核心持仓") is False
    panel.update_quote("600519", name="贵州茅台", price=1488, change=1.25)
    assert [panel._table.item(0, c).text() for c in range(4)] == [
        "600519",
        "贵州茅台",
        "1488",
        "+1.25%",
    ]


def test_watchlist_panel_keeps_group_column_compact_and_hides_row_numbers(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"全部": ["600519"]})
    qtbot.addWidget(panel)
    panel.resize(900, 600)
    panel.show()
    qtbot.waitExposed(panel)
    assert panel._group_column.maximumWidth() <= 180
    assert not panel._table.verticalHeader().isVisible()
    assert "border: none" in panel._group_list.styleSheet()
    assert "border: none" in panel._table.styleSheet()
    assert panel._group_list.height() < 300
    assert panel._table.geometry().bottom() >= panel._stock_column.height() - 36
    assert panel._add_group_btn.parentWidget() is panel._group_column
    assert panel._add_symbol_btn.parentWidget() is panel._stock_column


def test_watchlist_panel_resolves_common_a_share_names_from_code(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"全部": ["600510", "600520"]})
    qtbot.addWidget(panel)
    assert panel._table.item(0, 1).text() == "黑牡丹"
    assert panel._table.item(1, 1).text() == "文一科技"


def test_watchlist_panel_resolves_301526_name_from_code(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"全部": ["301526"]})
    qtbot.addWidget(panel)
    assert panel._table.item(0, 1).text() == "国际复材"


def test_watchlist_panel_decision_colors_by_local_day(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel(["600519"])
    qtbot.addWidget(panel)
    panel.update_decision("600519", "买入", date.today())
    assert panel._table.item(0, 4).foreground().color().name() == "#f85149"
    panel.update_decision("600519", "卖出", date.today())
    assert panel._table.item(0, 4).foreground().color().name() == "#3fb950"
    panel.update_decision("600519", "买入", date.today() - timedelta(days=1))
    assert panel._table.item(0, 4).foreground().color().name() != "#f85149"


def test_watchlist_panel_rename_and_protect_all_group(qtbot) -> None:
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel(["600519"])
    qtbot.addWidget(panel)
    assert panel.rename_group("全部", "核心") is False
    assert panel.remove_current_group() is False
    assert panel.add_group("观察") is True
    assert panel.rename_group("观察", "核心") is True
    assert panel.groups() == {"全部": ["600519"], "核心": []}


def test_watchlist_decision_adapter_preserves_record_day() -> None:
    from pa_agent.gui.watchlist_decisions import decision_for_record

    record = SimpleNamespace(
        stage2_decision={"decision": {"order_type": "市价单", "order_direction": "多"}},
        meta=SimpleNamespace(timestamp_local_iso="2026-08-28T09:30:00+08:00"),
    )
    assert decision_for_record(record) == ("买入", date(2026, 8, 28))


def test_watchlist_decision_adapter_handles_missing_stage2_payload() -> None:
    from pa_agent.gui.watchlist_decisions import decision_for_record

    assert decision_for_record(SimpleNamespace(stage2_decision=None, meta=None)) == ("", None)


def test_persist_watchlist_writes_groups_and_flat_compatibility(monkeypatch) -> None:
    from pa_agent.gui.main_window import MainWindow
    from pa_agent.gui.watchlist_panel import WatchlistPanel

    panel = WatchlistPanel({"全部": ["600519"], "观察": ["000001", "600519"]})
    settings = SimpleNamespace(general=SimpleNamespace(watchlist=[], watchlist_groups={}))
    window = MainWindow.__new__(MainWindow)
    window._watchlist_panel = panel
    window._ctx = SimpleNamespace(settings=settings)
    saved: list[object] = []
    monkeypatch.setattr("pa_agent.config.settings.save_settings", lambda value: saved.append(value))
    window._persist_watchlist()
    assert settings.general.watchlist_groups == {"全部": ["600519"], "观察": ["000001", "600519"]}
    assert settings.general.watchlist == ["600519", "000001"]
    assert saved == [settings]


# ── MainWindow wiring ─────────────────────────────────────────────────────────


def test_is_ashare_symbol_detection() -> None:
    window = _make_window()
    for sym in ("600519", "000001", "000300", "sh000300", "399006"):
        assert window._is_ashare_symbol(sym), sym
    for sym in ("XAUUSD", "BTCUSDT", "小米集团", "1810", ""):
        assert not window._is_ashare_symbol(sym), sym


def test_domestic_source_prefers_current_connected_domestic() -> None:
    window = _make_window(_active_data_source_kind="tencent")
    assert window._domestic_source_kind_for_ashare("600519") == "tencent"


def test_domestic_source_skips_unconnected_current() -> None:
    window = _make_window(
        _active_data_source_kind="tencent",
        _ctx=SimpleNamespace(data_source=SimpleNamespace(_connected=False), settings=None),
    )
    _seed_cache(("tencent",))
    assert window._domestic_source_kind_for_ashare("600519") == "tencent"


def test_domestic_source_uses_probe_cache() -> None:
    window = _make_window()  # current = tradingview
    _seed_cache(("tdx",))
    assert window._domestic_source_kind_for_ashare("600519") == "tdx"


def test_domestic_source_none_when_nothing_connected() -> None:
    window = _make_window()
    _seed_cache(())
    assert window._domestic_source_kind_for_ashare("600519") is None


def test_watchlist_select_non_ashare_switches_daily() -> None:
    window = _make_window()
    captured: dict[str, str] = {}
    window._apply_watchlist_switch = lambda sym, tf: captured.update(symbol=sym, tf=tf)
    window._on_watchlist_symbol_selected("XAUUSD")
    assert captured == {"symbol": "XAUUSD", "tf": "1d"}


def test_watchlist_select_ashare_no_source_switch_when_current_ok() -> None:
    window = _make_window(_active_data_source_kind="tencent")
    calls: list = []
    window._select_data_source_kind = lambda kind, switch: calls.append(("switch", kind))
    window._apply_watchlist_switch = lambda sym, tf: calls.append((sym, tf))
    window._on_watchlist_symbol_selected("600519")
    # current source already domestic & connected → only symbol/tf switch
    assert calls == [("600519", "1d")]


def test_watchlist_select_ashare_switches_source_from_tradingview() -> None:
    window = _make_window()  # current = tradingview
    _seed_cache(("tencent",))
    calls: list = []
    window._select_data_source_kind = lambda kind, switch: calls.append(("switch", kind))
    window._apply_watchlist_switch = lambda sym, tf: calls.append((sym, tf))
    window._on_watchlist_symbol_selected("600519")
    assert calls == [("switch", "tencent"), ("600519", "1d")]


def test_watchlist_select_ashare_kicks_probe_when_unknown() -> None:
    window = _make_window()
    _seed_cache(())
    started: dict[str, str] = {}
    window._apply_watchlist_switch = lambda sym, tf: None
    window._start_ashare_source_probe = lambda sym, tf: started.update(symbol=sym, tf=tf)
    window._on_watchlist_symbol_selected("600519")
    assert started == {"symbol": "600519", "tf": "1d"}


# ── factory probe helpers ─────────────────────────────────────────────────────


def test_first_connected_a_share_source_serves_cache() -> None:
    import pa_agent.data.factory as factory_mod

    _seed_cache(("eastmoney", "akshare"))
    assert factory_mod.first_connected_a_share_source() == "eastmoney"


def test_first_connected_a_share_source_none_when_all_fail() -> None:
    import pa_agent.data.factory as factory_mod

    _seed_cache(())
    assert factory_mod.first_connected_a_share_source() is None


def test_probed_status_does_not_probe_when_cache_fresh(monkeypatch) -> None:
    import pa_agent.data.factory as factory_mod

    _seed_cache(("tencent",))
    probed: list[str] = []
    monkeypatch.setattr(
        factory_mod,
        "probe_data_source",
        lambda kind, timeout_s=25.0: (probed.append(kind) or True, "ok"),
    )
    status = factory_mod.probed_a_share_source_status()
    assert probed == []  # all served from cache
    assert status["tencent"] == (True, "ok")

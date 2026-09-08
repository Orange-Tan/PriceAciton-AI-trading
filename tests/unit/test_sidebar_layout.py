"""Regression tests for the right-sidebar status/summary layout."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QScrollArea
from PyQt6.QtWidgets import QLabel, QToolButton
from PyQt6.QtWidgets import QSplitter

from pa_agent.app_context import AppContext
from pa_agent.config.settings import Settings
from pa_agent.gui.ai_stream_window import AIStreamPanel
from pa_agent.gui.decision_panel import DecisionPanel
from pa_agent.gui.theme import tokens as T
from pa_agent.gui.theme import apply as theme_apply
from pa_agent.util.event_bus import EventBus

_APP: QApplication | None = None


def _qapp() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    _APP = app
    return app


def test_realtime_panel_exposes_single_line_status_with_error_color():
    _qapp()
    panel = AIStreamPanel()
    panel.set_status("分析完成 · 可继续追问")
    assert panel._status_label.text() == "分析完成 · 可继续追问"
    assert T.SUCCESS in panel._status_label.styleSheet()

    panel.set_status("数据源连接异常")
    assert T.DANGER in panel._status_label.styleSheet()


def test_decision_panel_consolidates_summary_metrics_into_diagnosis():
    _qapp()
    panel = DecisionPanel()
    assert not hasattr(panel, "summary_strip")
    panel.set_summary_metrics(
        {
            "当前趋势": "震荡",
            "当前市场周期": "交易区间",
            "下一个市场周期": "下跌趋势",
            "支撑区": "27.73",
            "阻力区": "31.20",
        }
    )
    assert panel._trend_label.text() == "趋势：震荡"
    assert panel._cycle_label.text() == "周期：交易区间"
    assert panel._next_cycle_label.text() == "下一周期：下跌趋势"
    assert panel._support_label.text() == "支撑区：27.73"
    assert panel._resistance_label.text() == "阻力区：31.20"


def test_decision_title_row_contains_disclaimer_and_details_start_expanded():
    _qapp()
    panel = DecisionPanel()
    assert panel._title_label.parentWidget() is panel._disclaimer_label.parentWidget()
    assert panel._disclaimer_label.text() == "分析仅供参考，不构成投资建议"
    assert not panel.findChildren(QToolButton)
    assert not panel._reasoning_edit.isHidden()
    assert not panel._confidence_reasoning_edit.isHidden()
    assert not panel._risk_reasoning_edit.isHidden()


def test_analysis_settings_tab_precedes_realtime_tab():
    from pa_agent.gui.ai_sidebar import AISidebar

    _qapp()
    sidebar = AISidebar()
    assert sidebar._tabs.tabText(0) == "分析设置"
    assert sidebar._tabs.tabText(1) == "实时"
    assert sidebar._tabs.currentIndex() == sidebar.TAB_STREAM
    assert sidebar.analysis_settings is sidebar._tabs.widget(0)


def test_decision_tab_follows_realtime_before_decision_tree():
    from pa_agent.gui.ai_sidebar import AISidebar

    _qapp()
    sidebar = AISidebar()
    assert [sidebar._tabs.tabText(i) for i in range(4)] == [
        "分析设置", "实时", "决策", "决策树"
    ]
    assert sidebar.TAB_DECISION == 2
    assert sidebar.TAB_DECISION_TREE == 3


def test_decision_tab_is_wrapped_by_single_vertical_scroll_area():
    _qapp()
    from pa_agent.gui.ai_sidebar import AISidebar

    sidebar = AISidebar()
    assert sidebar._tabs.tabText(sidebar.TAB_DECISION) == "决策"
    scroll = sidebar._tabs.widget(sidebar.TAB_DECISION)
    assert isinstance(scroll, QScrollArea)
    assert scroll.widget() is sidebar.decision
    assert scroll.widgetResizable()


def test_analysis_settings_accepts_main_window_controls():
    from pa_agent.gui.ai_sidebar import AISidebar

    _qapp()
    sidebar = AISidebar()
    content = QLabel("controls")
    sidebar.set_analysis_settings_content(content)
    assert content.parentWidget() is sidebar.analysis_settings
    assert sidebar.analysis_settings.findChildren(QLabel, "")[0].text() == "controls"


def test_watchlist_panel_is_compact_and_resizable():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    window.resize(1400, 900)
    window.show()
    _qapp().processEvents()
    panel = window._watchlist_panel
    splitter = panel.parentWidget()
    assert isinstance(splitter, QSplitter)
    assert panel.minimumWidth() <= 240
    assert panel.maximumWidth() >= 420
    assert splitter.handleWidth() > 0
    assert splitter.handle(1).isEnabled()
    window.close()


def test_api_key_alert_lives_inside_analysis_settings():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    assert window._api_key_alert_label.parentWidget() is window._analysis_settings_content
    assert window._api_key_alert_label in window._analysis_settings_content.findChildren(QLabel)
    window.close()


def test_workbench_uses_zero_outer_spacing():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    layout = window.centralWidget().layout()
    assert layout is not None
    margins = layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    assert layout.spacing() == 0
    window.close()


def test_analysis_toolbar_is_single_row_in_requested_order():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    window.show()
    _qapp().processEvents()
    toolbar = window.findChild(QScrollArea, "analysisToolbarScroll")
    assert toolbar is not None
    row = toolbar.widget().layout()
    assert row is not None
    assert row.count() >= 8
    assert toolbar.widget().minimumHeight() > 0
    widgets = [row.itemAt(i).widget() for i in range(row.count())]
    widgets = [widget for widget in widgets if widget is not None]
    assert widgets.index(window._data_source_combo) < widgets.index(window._tv_exchange_combo)
    assert widgets.index(window._tv_exchange_combo) < widgets.index(window._symbol_combo)
    assert widgets.index(window._symbol_combo) < widgets.index(window._tf_combo)
    assert widgets.index(window._tf_combo) < widgets.index(window._fetch_data_btn)
    assert widgets.index(window._fetch_data_btn) < widgets.index(window._submit_btn)
    window.close()


def test_analysis_toolbar_hides_wait_controls_and_has_settings_button():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    window.show()
    _qapp().processEvents()
    toolbar = window.findChild(QScrollArea, "analysisToolbarScroll")
    assert toolbar is not None
    assert not window._wait_close_checkbox.isVisible()
    assert not window._wait_close_countdown_label.isVisible()
    settings_button = window.findChild(QToolButton, "analysisSettingsButton")
    assert settings_button is not None
    assert settings_button.isVisible()
    window.close()


def test_instrument_kind_only_shows_when_explicitly_provided_by_source():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    source = SimpleNamespace(_connected=False, instrument_kind="期货")
    ctx = AppContext(settings=Settings(), event_bus=EventBus(), data_source=source)
    window = MainWindow(ctx)
    window.show()
    _qapp().processEvents()
    assert window._instrument_kind_combo.isVisible()
    assert window._instrument_kind_combo.currentText() == "期货"
    window.close()


def test_instrument_kind_is_hidden_when_source_has_no_explicit_metadata():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    source = SimpleNamespace(_connected=False)
    ctx = AppContext(settings=Settings(), event_bus=EventBus(), data_source=source)
    window = MainWindow(ctx)
    window.show()
    _qapp().processEvents()
    assert not window._instrument_kind_label.isVisible()
    assert not window._instrument_kind_combo.isVisible()
    window.close()


def test_instrument_kind_ignores_response_metadata_without_source_field():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    source = SimpleNamespace(
        _connected=False,
        response={"instrument_kind": "期货"},
        metadata={"asset_type": "期货"},
    )
    ctx = AppContext(settings=Settings(), event_bus=EventBus(), data_source=source)
    window = MainWindow(ctx)
    window.show()
    _qapp().processEvents()
    assert not window._instrument_kind_label.isVisible()
    assert not window._instrument_kind_combo.isVisible()
    window.close()


def test_analysis_toolbar_replaces_sidebar_parameter_rows_and_keeps_fit_in_chart_toolbar():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    window.resize(1400, 900)
    window.show()
    _qapp().processEvents()

    assert window._symbol_label.text() == "代码/名称:"
    assert window._tf_label.text() == "周期:"
    assert window._resume_chart_btn.parentWidget() is window._analysis_toolbar_scroll.widget()
    assert window._fit_chart_btn.parentWidget() is window._chart_toolbar
    assert window._keep_analysis_checkbox.parentWidget() is window._analysis_toolbar_scroll.widget()
    window.close()


def test_analysis_settings_has_top_status_strip_matching_prototype_hierarchy():
    from pa_agent.gui.main_window import MainWindow

    _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    assert window._status_strip.parentWidget() is window._analysis_settings_content
    assert window._decision_badge.parentWidget() is window._status_strip
    assert window._ai_mode_label.parentWidget() is window._status_strip
    assert "font-size: 16px" in window._decision_badge.styleSheet()
    assert "font-size: 14px" in window._ai_mode_label.styleSheet()
    window._analysis_in_progress = True
    window._on_status_update("阶段一分析中…")
    assert window._decision_badge.text() == "● 分析中…"
    assert window._ai_mode_label.text() == (
        f"深度求索 DeepSeek · {window._ctx.settings.provider.model}"
    )
    window.close()


def test_light_theme_is_the_default_for_new_settings():
    assert Settings().general.theme == "light"
    assert theme_apply._DEFAULT_KIND == "light"


def test_menu_bar_toggle_hides_and_restores_ai_sidebar():
    from pa_agent.gui.main_window import MainWindow

    app = _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    window.resize(1400, 900)
    window.show()
    app.processEvents()

    assert window._right_sidebar_toggle_button.toolTip() == "隐藏右侧栏"
    window._toggle_ai_sidebar()
    assert window._ai_sidebar.isHidden()
    assert window._right_sidebar_toggle_button.toolTip() == "显示右侧栏"
    window._toggle_ai_sidebar()
    app.processEvents()
    assert window._ai_sidebar.isVisible()
    window.close()


def test_workbench_initializes_ai_sidebar_to_one_third_width():
    from pa_agent.gui.main_window import MainWindow

    app = _qapp()
    ctx = AppContext(
        settings=Settings(),
        event_bus=EventBus(),
        data_source=SimpleNamespace(_connected=False),
    )
    window = MainWindow(ctx)
    window.resize(1500, 900)
    window.show()
    app.processEvents()
    sizes = window._workbench.sizes()

    assert abs(sizes[2] - sum(sizes) / 3) <= 3
    window.close()

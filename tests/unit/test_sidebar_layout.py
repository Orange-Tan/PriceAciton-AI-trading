"""Regression tests for the right-sidebar status/summary layout."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QLabel
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


def test_decision_panel_contains_integrated_summary_strip():
    _qapp()
    panel = DecisionPanel()
    assert panel.summary_strip.parent() is panel
    panel.summary_strip.set_metrics({"当前趋势": "震荡"})
    assert panel.summary_strip._cards[0]._value.text() == "震荡"


def test_analysis_settings_tab_precedes_realtime_tab():
    from pa_agent.gui.ai_sidebar import AISidebar

    _qapp()
    sidebar = AISidebar()
    assert sidebar._tabs.tabText(0) == "分析设置"
    assert sidebar._tabs.tabText(1) == "实时"
    assert sidebar._tabs.currentIndex() == sidebar.TAB_STREAM
    assert sidebar.analysis_settings is sidebar._tabs.widget(0)


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


def test_light_theme_is_the_default_for_new_settings():
    assert Settings().general.theme == "light"
    assert theme_apply._DEFAULT_KIND == "light"

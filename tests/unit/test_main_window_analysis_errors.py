"""Regression tests for analysis exception reporting in MainWindow."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6")


def _record_with_provider_error() -> SimpleNamespace:
    return SimpleNamespace(
        exception={
            "stage": "stage1",
            "type": "provider_error",
            "category": "e",
            "message": "provider unavailable",
        },
        stage1_messages=[],
        stage1_response={},
        stage1_diagnosis=None,
        stage2_messages=[],
        stage2_response={},
        stage2_decision=None,
        strategy_files_used=[],
        experience_loaded=[],
    )


def _window(monkeypatch, debug_widget) -> tuple[object, list[tuple[str, str]], list[tuple]]:
    from pa_agent.gui.main_window import MainWindow

    status_messages: list[str] = []
    debug_reports: list[tuple] = []
    window = MainWindow.__new__(MainWindow)
    window._debug_widget = debug_widget
    window._prompt_files_panel = None
    window._stream_panel = None
    window._ctx = SimpleNamespace(settings=None)
    window._status_bar = SimpleNamespace(showMessage=status_messages.append)
    window._ui_is_alive = lambda: True
    window._maybe_show_truncation_help_dialog = lambda _exc_info: None
    window._prompt_debug_report_for_bug_fix = lambda *args, **kwargs: debug_reports.append((args, kwargs))
    return window, status_messages, debug_reports


def test_provider_error_is_reported_when_debug_widget_is_missing(monkeypatch) -> None:
    window, status_messages, debug_reports = _window(monkeypatch, None)

    window._on_record_ready(_record_with_provider_error())

    assert window._last_analysis_had_error is True
    assert status_messages == ["provider unavailable"]
    assert debug_reports and debug_reports[0][0][0] == "API 积分不足"


def test_provider_error_is_reported_when_debug_widget_is_destroyed(monkeypatch) -> None:
    class _DestroyedDebugWidget:
        def add_turn(self, _turn) -> None:
            raise RuntimeError("wrapped C/C++ object has been deleted")

    window, status_messages, debug_reports = _window(monkeypatch, _DestroyedDebugWidget())

    window._on_record_ready(_record_with_provider_error())

    assert window._last_analysis_had_error is True
    assert status_messages == ["provider unavailable"]
    assert debug_reports and debug_reports[0][0][0] == "API 积分不足"

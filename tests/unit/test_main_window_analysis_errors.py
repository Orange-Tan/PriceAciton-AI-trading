"""Regression tests for silent analysis completion in MainWindow."""
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


def _window(debug_widget) -> tuple[object, list[str], list[tuple]]:
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
    window._keep_analysis_checkbox = None
    window._chart_refresh_paused = False
    window._prompt_debug_report_for_bug_fix = lambda *args, **kwargs: debug_reports.append((args, kwargs))
    return window, status_messages, debug_reports


def test_provider_error_record_completion_does_not_prompt_dialogs() -> None:
    window, status_messages, debug_reports = _window(None)

    window._on_record_ready(_record_with_provider_error())

    assert window._last_analysis_had_error is True
    assert status_messages == ["provider unavailable"]
    assert debug_reports == []


def test_unhandled_analysis_error_does_not_prompt_dialogs() -> None:
    class _DebugWidget:
        def __init__(self) -> None:
            self.turns: list[dict] = []

        def add_turn(self, turn) -> None:
            self.turns.append(turn)

    debug_widget = _DebugWidget()
    window, status_messages, debug_reports = _window(debug_widget)

    window._on_analysis_error("boom")

    assert window._last_analysis_had_error is True
    assert debug_widget.turns == [
        {
            "label": "⚠ 程序异常",
            "system_prompt": "",
            "user_prompt": "",
            "raw_response": {},
            "validation_info": "boom",
        }
    ]
    assert status_messages == []
    assert debug_reports == []


def test_worker_done_still_writes_completion_status_without_prompting() -> None:
    window, status_messages, debug_reports = _window(None)
    window._last_analysis_had_error = False
    window._maybe_auto_resume_chart_after_analysis = lambda: False
    window._refresh_keep_analysis_sentinel = lambda: None
    window._reap_zombie_workers = lambda: None
    window._reap_zombie_loops = lambda: None
    window._update_submit_button_state = lambda: None
    window._set_chart_refresh_paused = lambda _paused: None

    window._on_worker_done()

    assert status_messages == ["分析完成"]
    assert debug_reports == []

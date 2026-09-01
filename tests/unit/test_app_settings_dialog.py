from __future__ import annotations

from pa_agent.config.settings import Settings


def test_reject_stops_probe_worker(qtbot, monkeypatch):
    from pa_agent.gui.app_settings_dialog import AppSettingsDialog

    dialog = AppSettingsDialog(Settings())
    qtbot.addWidget(dialog)
    called = []
    monkeypatch.setattr(dialog, "_shutdown_probe_worker", lambda: called.append(True))

    dialog.reject()

    assert called == [True]

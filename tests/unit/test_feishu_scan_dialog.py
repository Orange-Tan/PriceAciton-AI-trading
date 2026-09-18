from __future__ import annotations

from types import SimpleNamespace

from pa_agent.config.settings import Settings


def test_scan_dialog_cancel_detaches_running_worker(qtbot, monkeypatch):
    from pa_agent.gui.feishu_scan_dialog import FeishuScanDialog

    monkeypatch.setattr(
        "pa_agent.gui.feishu_scan_dialog.FeishuScanWorker.start", lambda _self: None
    )
    dialog = FeishuScanDialog(Settings())
    qtbot.addWidget(dialog)
    calls: list[str] = []

    class RunningWorker(SimpleNamespace):
        def isRunning(self):
            return True

        def stop(self):
            calls.append("stop")

        def setParent(self, parent):
            calls.append(f"parent:{parent}")

        def deleteLater(self):
            calls.append("delete")

        class Signal:
            def disconnect(self):
                calls.append("disconnect")

            def connect(self, _slot):
                calls.append("connect")

        qr_ready = status_changed = success = failed = finished = Signal()

    worker = RunningWorker()
    dialog._worker = worker
    dialog.reject()

    assert "stop" in calls
    assert "parent:None" in calls

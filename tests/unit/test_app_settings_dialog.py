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


def test_model_api_page_exposes_connection_test(qtbot):
    from pa_agent.gui.app_settings_dialog import AppSettingsDialog

    dialog = AppSettingsDialog(Settings())
    qtbot.addWidget(dialog)

    assert dialog._model_probe_btn.text() == "测试模型连接"
    assert dialog._model_probe_label.text() == ""


def test_model_probe_worker_reports_success_without_network(monkeypatch):
    from pa_agent.gui.app_settings_dialog import _ModelProbeWorker

    class FakeClient:
        def __init__(self, settings):
            self.settings = settings

        def chat(self, messages, **kwargs):
            assert messages[0]["content"] == "只回复 OK"
            assert kwargs["timeout_s"] <= 30
            return object()

    monkeypatch.setattr("pa_agent.ai.deepseek_client.DeepSeekClient", FakeClient)
    worker = _ModelProbeWorker(Settings().provider)
    result = []
    worker.probed.connect(lambda ok, detail: result.append((ok, detail)))
    worker.run()

    assert result == [(True, "模型连通正常")]


def test_model_probe_worker_masks_api_key_on_failure(monkeypatch):
    from pa_agent.gui.app_settings_dialog import _ModelProbeWorker

    class FakeClient:
        def __init__(self, settings):
            self.settings = settings

        def chat(self, _messages, **_kwargs):
            raise RuntimeError(f"unauthorized key={self.settings.api_key}")

    monkeypatch.setattr("pa_agent.ai.deepseek_client.DeepSeekClient", FakeClient)
    settings = Settings().provider
    settings.api_key = "token-secret-test-key"
    worker = _ModelProbeWorker(settings)
    result = []
    worker.probed.connect(lambda ok, detail: result.append((ok, detail)))
    worker.run()

    assert result[0][0] is False
    assert settings.api_key not in result[0][1]

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


def test_editable_model_text_wins_over_stale_combo_data(qtbot):
    from pa_agent.gui.app_settings_dialog import AppSettingsDialog

    dialog = AppSettingsDialog(Settings())
    qtbot.addWidget(dialog)
    dialog._model_combo.setCurrentText("gpt-5.6-luna")

    assert dialog._model_form_value() == "gpt-5.6-luna"


def test_switching_provider_does_not_reuse_previous_api_key(qtbot):
    from pa_agent.gui.app_settings_dialog import AppSettingsDialog

    settings = Settings()
    settings.provider.api_key = "token-deepseek-value"
    dialog = AppSettingsDialog(settings)
    qtbot.addWidget(dialog)
    openai_index = dialog._provider_combo.findData("openai")
    assert openai_index >= 0

    dialog._provider_combo.setCurrentIndex(openai_index)

    assert dialog._api_key_edit.text() == ""
    assert dialog._api_key_edit.placeholderText() == "输入 API Key"


def test_existing_api_key_is_not_rendered_as_plaintext(qtbot):
    from PyQt6.QtWidgets import QLineEdit
    from pa_agent.gui.app_settings_dialog import AppSettingsDialog

    settings = Settings()
    settings.provider.api_key = "token-existing-value"
    dialog = AppSettingsDialog(settings)
    qtbot.addWidget(dialog)

    assert dialog._api_key_edit.echoMode() == QLineEdit.EchoMode.Password
    assert dialog._api_key_edit.text() == ""
    assert dialog._api_key_edit.placeholderText() == "已输入"


def test_save_preserves_existing_key_when_field_is_untouched(qtbot, monkeypatch):
    from pa_agent.gui.app_settings_dialog import AppSettingsDialog

    settings = Settings()
    settings.provider.api_key = "token-existing-value"
    dialog = AppSettingsDialog(settings)
    qtbot.addWidget(dialog)
    monkeypatch.setattr("pa_agent.gui.app_settings_dialog.save_settings", lambda *_: None)
    monkeypatch.setattr(dialog, "accept", lambda: None)

    dialog._on_save()

    assert settings.provider.api_key == "token-existing-value"

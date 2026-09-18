from __future__ import annotations

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


class _Source:
    def __init__(self, *, fail_connect: bool = False) -> None:
        self.fail_connect = fail_connect
        self.connected = False
        self.subscriptions: list[tuple[str, str]] = []

    def unsubscribe(self) -> None:
        pass

    def disconnect(self) -> None:
        self.connected = False

    def connect(self) -> None:
        if self.fail_connect:
            raise RuntimeError("new source unavailable")
        self.connected = True

    def subscribe(self, symbol: str, timeframe: str) -> None:
        self.subscriptions.append((symbol, timeframe))


def test_switch_failure_restores_previous_source(monkeypatch) -> None:
    from pa_agent.gui.main_window import MainWindow

    old_source = _Source()
    new_source = _Source(fail_connect=True)
    monkeypatch.setattr("pa_agent.data.factory.create_data_source", lambda _kind: new_source)

    window = MainWindow.__new__(MainWindow)
    window._switching = False
    window._active_data_source_kind = "tradingview"
    window._ctx = SimpleNamespace(data_source=old_source, settings=None)
    window._symbol_combo = _Combo("XAUUSD")
    window._tf_combo = _Combo("15m")
    window._tv_exchange_combo = _Combo("")
    window._cancel_analysis_worker = lambda: None
    window._update_submit_button_state = lambda: None
    window._ui_is_alive = lambda: False
    window._stop_refresh_loop = lambda: None
    window._disconnect_data_source = lambda source: source.disconnect()
    window._sync_tv_exchange_visibility = lambda: None
    window._apply_gold_defaults_for_data_source = lambda _kind: None
    window._tv_exchange_text = lambda: ""

    with pytest.raises(RuntimeError, match="new source unavailable"):
        window._switch_data_source("tencent")

    assert window._active_data_source_kind == "tradingview"
    assert window._ctx.data_source is old_source
    assert old_source.connected is True
    assert old_source.subscriptions == [("XAUUSD", "15m")]

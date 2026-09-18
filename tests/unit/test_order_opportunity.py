"""Tests for order-opportunity detection."""

from __future__ import annotations

from pa_agent.gui.order_opportunity import (
    _windows_alert_wav_paths,
    format_order_alert_message,
    has_order_opportunity,
    play_order_alert_sound,
)


def test_has_order_opportunity_for_active_orders() -> None:
    for order_type in ("限价单", "突破单", "市价单"):
        assert has_order_opportunity({"order_type": order_type})


def test_no_order_opportunity_when_wait() -> None:
    assert not has_order_opportunity({"order_type": "不下单"})
    assert not has_order_opportunity({})


def test_format_order_alert_message_includes_prices() -> None:
    text = format_order_alert_message(
        {
            "order_direction": "做多",
            "order_type": "突破单",
            "entry_price": 2650.5,
            "stop_loss_price": 2640,
            "take_profit_price": 2670,
            "reasoning": "测试理由",
        }
    )
    assert "做多" in text
    assert "突破单" in text
    assert "2650.5" in text
    assert "决策" in text


def test_windows_alert_wav_paths_include_notify() -> None:
    paths = _windows_alert_wav_paths()
    assert any(p.endswith("notify.wav") for p in paths)


def test_order_alert_auto_close_constant() -> None:
    from pa_agent.gui.order_opportunity import ORDER_ALERT_AUTO_CLOSE_MS

    assert ORDER_ALERT_AUTO_CLOSE_MS == 120_000


def test_play_order_alert_sound_uses_wav_on_windows(monkeypatch) -> None:
    played: list[str] = []

    class FakeWinsound:
        SND_FILENAME = 1
        SND_ALIAS = 2
        SND_NODEFAULT = 4
        MB_ICONEXCLAMATION = 48

        @staticmethod
        def PlaySound(name, flags):
            played.append(str(name))

        @staticmethod
        def MessageBeep(_kind):
            played.append("MessageBeep")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setitem(__import__("sys").modules, "winsound", FakeWinsound())
    monkeypatch.setattr(
        "pa_agent.gui.order_opportunity.os.path.isfile",
        lambda p: str(p).endswith("notify.wav"),
    )

    assert play_order_alert_sound() is True
    assert played and played[0].endswith("notify.wav")


def test_analysis_order_opportunity_does_not_open_popup(monkeypatch) -> None:
    from types import SimpleNamespace

    from pa_agent.gui.main_window import MainWindow

    popup_calls: list[dict] = []
    monkeypatch.setattr("pa_agent.gui.order_opportunity.play_order_alert_sound", lambda: True)
    monkeypatch.setattr(
        "pa_agent.gui.order_opportunity.show_order_opportunity_alert",
        lambda _parent, decision: popup_calls.append(decision),
    )
    window = MainWindow.__new__(MainWindow)
    window._order_opportunity_alert_enabled = lambda: True
    window._has_order_opportunity = lambda _decision: True
    window._ai_sidebar = SimpleNamespace(focus_decision=lambda: None)

    assert window._maybe_alert_order_opportunity({"order_type": "限价单"}) is True
    assert popup_calls == []

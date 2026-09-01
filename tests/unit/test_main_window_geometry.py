from types import SimpleNamespace

from pa_agent.gui.main_window import _default_window_size


def test_default_window_size_uses_90_percent_of_available_geometry() -> None:
    screen = SimpleNamespace(
        availableGeometry=lambda: SimpleNamespace(width=lambda: 1407, height=lambda: 923)
    )

    assert _default_window_size(screen) == (1266, 830)


def test_default_window_size_uses_fallback_without_screen() -> None:
    assert _default_window_size(None) == (1280, 820)


def test_default_window_size_uses_fallback_without_available_geometry() -> None:
    screen = SimpleNamespace(availableGeometry=lambda: None)

    assert _default_window_size(screen) == (1280, 820)


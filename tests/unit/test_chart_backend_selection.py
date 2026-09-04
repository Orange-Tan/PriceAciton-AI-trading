from pathlib import Path

from pa_agent.gui.tradingview_chart_widget import klinechart_available, tradingview_available


def test_klinechart_backend_aliases_are_consistent() -> None:
    assert klinechart_available() is tradingview_available()


def test_main_window_selects_klinechart_backend() -> None:
    source = (
        Path(__file__).parents[2] / "pa_agent" / "gui" / "main_window.py"
    ).read_text(encoding="utf-8")
    assert "klinechart_available" in source
    assert "Using embedded KLineChart" in source


def test_klinechart_static_assets_exist() -> None:
    root = Path(__file__).parents[2] / "tradingview" / "klinechart"
    assert (root / "klinecharts.min.js").is_file()
    assert (root / "LICENSE").is_file()
    assert (root / "NOTICE").is_file()

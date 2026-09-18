from pathlib import Path

from pa_agent.gui.klinechart_widget import KLineChartWidget, klinechart_available


def test_klinechart_backend_uses_the_new_widget_name() -> None:
    assert KLineChartWidget.__name__ == "KLineChartWidget"
    assert isinstance(klinechart_available(), bool)


def test_main_window_selects_klinechart_backend() -> None:
    source = (Path(__file__).parents[2] / "pa_agent" / "gui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    assert "klinechart_available" in source
    assert "KLineChartWidget" in source
    assert "TradingViewChartWidget" not in source
    assert "Using embedded KLineChart" in source


def test_klinechart_static_assets_exist() -> None:
    root = Path(__file__).parents[2] / "tradingview" / "klinechart"
    assert (root / "klinecharts.min.js").is_file()
    assert (root / "LICENSE").is_file()
    assert (root / "NOTICE").is_file()

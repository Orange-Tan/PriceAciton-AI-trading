from pathlib import Path

PAGE = Path(__file__).parents[2] / "tradingview" / "pa_agent_chart.html"


def test_chart_page_uses_local_klinechart_and_exposes_bridge_methods() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'src="klinechart/klinecharts.min.js"' in html
    assert "charting_library-master" not in html
    assert "datafeeds/udf" not in html
    for method in (
        "setData",
        "setContext",
        "updateData",
        "setProgramOverlays",
        "clearProgramOverlays",
        "setInteractionMode",
    ):
        assert f"{method}:" in html
    assert "setDataLoader" in html
    assert "resetData" in html
    assert "setFrame:" not in html


def test_chart_page_does_not_load_remote_scripts() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert "http://" not in html
    assert "https://" not in html

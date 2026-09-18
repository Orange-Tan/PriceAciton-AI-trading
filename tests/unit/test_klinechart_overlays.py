from pathlib import Path

PAGE = Path(__file__).parents[2] / "tradingview" / "pa_agent_chart.html"


def test_page_exposes_program_overlay_and_user_drawing_controls() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "horizontalStraightLine" in html
    assert "straightLine" in html
    assert 'data-overlay="paRect"' in html
    assert "groupId: 'program'" in html
    assert "groupId: 'user'" in html
    assert "removeOverlay({ groupId: 'user' })" in html


def test_page_uses_klinechart_timestamp_and_incremental_apis() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert "setDataLoader" in html
    assert "resetData" in html
    assert "updateData" in html
    assert "timestamp" in html

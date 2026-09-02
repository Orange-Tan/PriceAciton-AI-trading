"""Qt WebEngine host for the local TradingView Charting Library page."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QUrl

try:  # Optional until PyQt6-WebEngine is installed.
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - exercised only on minimal installs
    QWebEngineView = None  # type: ignore[assignment,misc]
    QWebEngineSettings = None  # type: ignore[assignment,misc]

from pa_agent.data.base import KlineFrame
from pa_agent.data.tradingview_udf import UDFDatafeedServer


def tradingview_available() -> bool:
    """Return whether the optional Qt WebEngine dependency is importable."""
    return QWebEngineView is not None


if QWebEngineView is not None:

    class TradingViewChartWidget(QWebEngineView):
        """TradingView-backed replacement implementing the ChartWidget surface."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self._frame: KlineFrame | None = None
            self._last_symbol: str = ""
            self._last_timeframe: str = ""
            self._ready = False
            self._server = UDFDatafeedServer(lambda: self._frame)
            self._feed_url = self._server.start()
            if QWebEngineSettings is not None:
                self.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                    True,
                )
            self.loadFinished.connect(self._on_loaded)
            page = Path(__file__).resolve().parents[2] / "tradingview" / "pa_agent_chart.html"
            url = QUrl.fromLocalFile(str(page))
            url.setQuery(f"feed={QUrl.toPercentEncoding(self._feed_url).data().decode()}" )
            self.load(url)

        def set_frame(self, frame: KlineFrame, *, fit_view: bool = False) -> None:
            self._frame = frame
            if self._ready:
                self._sync_frame(fit_view=fit_view)

        def set_frame_now(self, frame: KlineFrame, *, fit_view: bool = False) -> None:
            self.set_frame(frame, fit_view=fit_view)

        def reset(self) -> None:
            self._frame = None
            self._last_symbol = ""
            self._last_timeframe = ""

        def fit_view(self) -> None:
            if self._ready:
                self.page().runJavaScript("window.PAChart && window.PAChart.fit();")

        def request_fit_on_next_render(self) -> None:
            self.fit_view()

        def set_seq_label_font_pt(self, _point_size: int) -> None:
            """Compatibility no-op; sequence labels are rendered by TradingView."""
            return

        def displayed_frame(self) -> KlineFrame | None:
            return self._frame

        def set_decision(self, decision: dict[str, Any]) -> None:
            self._run_json("setDecision", decision)

        def clear_decision_overlay(self) -> None:
            self._run_json("setDecision", {})

        def set_support_resistance(self, levels: list[Any]) -> None:
            serialised = []
            for level in levels:
                price = getattr(level, "price", None)
                if price is None:
                    continue
                serialised.append({"price": float(price), "kind": getattr(level, "kind", "support")})
            self._run_json("setLevels", serialised)

        def clear_support_resistance(self) -> None:
            self._run_json("setLevels", [])

        def refresh_theme(self) -> None:
            # The page uses TradingView's light theme by default; callers can
            # later pass the application theme through this same bridge.
            return

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            self._server.stop()
            super().closeEvent(event)

        def _on_loaded(self, ok: bool) -> None:
            self._ready = bool(ok)
            if self._ready and self._frame is not None:
                self._sync_frame(fit_view=True)

        def _sync_frame(self, *, fit_view: bool) -> None:
            frame = self._frame
            if frame is None:
                return
            payload = {"symbol": frame.symbol, "timeframe": frame.timeframe}
            if (frame.symbol, frame.timeframe) != (self._last_symbol, self._last_timeframe):
                self._last_symbol, self._last_timeframe = frame.symbol, frame.timeframe
                self._run_json("setFrame", payload)
            if fit_view:
                self.fit_view()

        def _run_json(self, method: str, value: Any) -> None:
            if not self._ready:
                return
            script = f"window.PAChart && window.PAChart.{method}({json.dumps(value, ensure_ascii=False)});"
            self.page().runJavaScript(script)

else:

    class TradingViewChartWidget:  # pragma: no cover - import-time fallback only
        """Placeholder used when QtWebEngine is unavailable."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PyQt6-WebEngine is required for TradingView charts")

"""Qt WebEngine host for the local KLineChart page."""

from __future__ import annotations

import json
from contextlib import suppress
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


def klinechart_available() -> bool:
    """Return whether the optional Qt WebEngine dependency is importable."""
    return QWebEngineView is not None


def frame_to_klinechart_bars(frame: KlineFrame) -> list[dict[str, Any]]:
    """Convert the newest-first frame into ascending KLineChart bar objects."""
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for bar in sorted(frame.bars, key=lambda item: float(item.ts_open)):
        timestamp = int(float(bar.ts_open))
        if timestamp in seen:
            continue
        seen.add(timestamp)
        result.append(
            {
                "timestamp": timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "turnover": float(getattr(bar, "amount", 0.0)),
            }
        )
    return result


def levels_to_klinechart_overlays(levels: list[Any], frame: KlineFrame) -> list[dict[str, Any]]:
    """Convert StructureLevel-like objects into program horizontal overlays."""
    bars = frame_to_klinechart_bars(frame)
    if not bars:
        return []
    start_time = bars[0]["timestamp"]
    end_time = bars[-1]["timestamp"]
    overlays: list[dict[str, Any]] = []
    for index, level in enumerate(levels):
        price = getattr(level, "price", None)
        if price is None:
            continue
        kind = getattr(level, "kind", "support")
        overlays.append(
            {
                "id": f"sr-{index}",
                "type": "level",
                "price": float(price),
                "startTime": start_time,
                "endTime": end_time,
                "label": getattr(level, "label", "支撑" if kind == "support" else "阻力"),
                "color": "#22c55e" if kind == "support" else "#f59e0b",
                "width": 1,
                "style": "dashed",
            }
        )
    return overlays


def decision_to_klinechart_overlays(
    decision: dict[str, Any], frame: KlineFrame
) -> list[dict[str, Any]]:
    """Convert a trading decision into program price lines and a direction marker."""
    order_type = str(decision.get("order_type", "") or "").strip().lower()
    if order_type in {"不下单", "no_order", "no_trade", "notrade", "hold", "skip", "none", "wait"}:
        return []
    bars = frame_to_klinechart_bars(frame)
    if not bars:
        return []
    start_time = bars[0]["timestamp"]
    end_time = bars[-1]["timestamp"]
    specs = (
        ("entry_price", "Entry", "#3b82f6"),
        ("take_profit_price", "TP1", "#22c55e"),
        ("take_profit_price_2", "TP2", "#86efac"),
        ("stop_loss_price", "SL", "#ef4444"),
    )
    overlays: list[dict[str, Any]] = []
    for field, label, color in specs:
        price = decision.get(field)
        if price is None:
            continue
        try:
            price_float = float(price)
        except (TypeError, ValueError):
            continue
        overlays.append(
            {
                "id": f"decision-{field}",
                "type": "level",
                "price": price_float,
                "startTime": start_time,
                "endTime": end_time,
                "label": label,
                "color": color,
                "width": 1,
                "style": "dashed",
            }
        )

    entry = decision.get("entry_price")
    direction = str(decision.get("order_direction", "") or "")
    if entry is not None and direction in {"做多", "做空"}:
        with suppress(TypeError, ValueError):
            overlays.append(
                {
                    "id": "decision-direction",
                    "type": "marker",
                    "time": end_time,
                    "price": float(entry),
                    "text": "Buy" if direction == "做多" else "Sell",
                    "color": "#22c55e" if direction == "做多" else "#ef4444",
                }
            )
    return overlays


if QWebEngineView is not None:

    class KLineChartWidget(QWebEngineView):
        """KLineChart-backed replacement implementing the ChartWidget surface."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self._frame: KlineFrame | None = None
            self._last_frame_key: tuple[str, str] | None = None
            self._last_bars: list[dict[str, Any]] = []
            self._decision: dict[str, Any] | None = None
            self._levels: list[Any] = []
            self._last_overlay_signature = ""
            self._ready = False
            self._pending_fit = False
            if QWebEngineSettings is not None:
                self.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                    False,
                )
            self.loadFinished.connect(self._on_loaded)
            page = Path(__file__).resolve().parents[2] / "tradingview" / "pa_agent_chart.html"
            self.load(QUrl.fromLocalFile(str(page)))

        def set_frame(self, frame: KlineFrame, *, fit_view: bool = False) -> None:
            self._frame = frame
            self._pending_fit = self._pending_fit or fit_view
            if self._ready:
                self._sync_frame()

        def set_frame_now(self, frame: KlineFrame, *, fit_view: bool = False) -> None:
            self.set_frame(frame, fit_view=fit_view)

        def reset(self) -> None:
            self._frame = None
            self._last_frame_key = None
            self._last_bars = []
            self._decision = None
            self._levels = []
            self._last_overlay_signature = ""
            self._pending_fit = False
            self._run_json("clearProgramOverlays", None)
            self._run_json("setData", [])

        def fit_view(self) -> None:
            if self._ready:
                self.page().runJavaScript("window.PAChart && window.PAChart.fit();")
            else:
                self._pending_fit = True

        def request_fit_on_next_render(self) -> None:
            self.fit_view()

        def set_seq_label_font_pt(self, _point_size: int) -> None:
            """Compatibility no-op; sequence labels are rendered by KLineChart."""

        def displayed_frame(self) -> KlineFrame | None:
            return self._frame

        def set_decision(self, decision: dict[str, Any]) -> None:
            self._decision = dict(decision)
            self._sync_program_overlays()

        def clear_decision_overlay(self) -> None:
            self._decision = None
            self._sync_program_overlays()

        def set_support_resistance(self, levels: list[Any]) -> None:
            self._levels = list(levels)
            self._sync_program_overlays()

        def clear_support_resistance(self) -> None:
            self._levels = []
            self._sync_program_overlays()

        def refresh_theme(self) -> None:
            """Keep the KLineChart page theme stable with the existing chart surface."""

        def closeEvent(self, event: Any) -> None:
            super().closeEvent(event)

        def _on_loaded(self, ok: bool) -> None:
            self._ready = bool(ok)
            if self._ready:
                self._sync_frame()
                self._sync_program_overlays()
                if self._pending_fit:
                    self._pending_fit = False
                    self.fit_view()

        def _sync_frame(self) -> None:
            frame = self._frame
            if frame is None:
                return
            bars = frame_to_klinechart_bars(frame)
            frame_key = (frame.symbol, frame.timeframe)
            can_update_last = (
                frame_key == self._last_frame_key
                and len(bars) == len(self._last_bars)
                and len(bars) > 0
                and bars[:-1] == self._last_bars[:-1]
            )
            if frame_key != self._last_frame_key:
                self._run_json(
                    "setContext",
                    {"symbol": frame.symbol, "timeframe": frame.timeframe},
                )
            if can_update_last:
                self._run_json("updateData", bars[-1])
            else:
                self._run_json("setData", bars)
            self._last_frame_key = frame_key
            self._last_bars = bars
            self._sync_program_overlays()

        def _sync_program_overlays(self) -> None:
            if not self._ready or self._frame is None:
                return
            overlays = levels_to_klinechart_overlays(self._levels, self._frame)
            if self._decision is not None:
                overlays.extend(decision_to_klinechart_overlays(self._decision, self._frame))
            signature = json.dumps(overlays, ensure_ascii=False, sort_keys=True)
            if signature == self._last_overlay_signature:
                return
            self._last_overlay_signature = signature
            self._run_json("setProgramOverlays", overlays)

        def _run_json(self, method: str, value: Any) -> None:
            if not self._ready:
                return
            payload = "" if value is None else json.dumps(value, ensure_ascii=False)
            script = f"window.PAChart && window.PAChart.{method}({payload});"
            self.page().runJavaScript(script)

else:

    class KLineChartWidget:  # pragma: no cover - import-time fallback only
        """Placeholder used when QtWebEngine is unavailable."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PyQt6-WebEngine is required for KLineChart charts")

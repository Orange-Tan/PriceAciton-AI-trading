"""Small local UDF bridge for the embedded TradingView chart.

The charting library speaks HTTP UDF while PA Agent keeps market data in
``KlineFrame`` objects.  This module deliberately has no Qt dependency so it
can be exercised independently and hosted from a background thread.
"""
from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from pa_agent.data.base import KlineFrame


def udf_config() -> dict[str, Any]:
    """Return the UDF capabilities used by the embedded chart."""
    return {
        "supports_search": True,
        "supports_group_request": False,
        "supports_marks": False,
        "supports_timescale_marks": False,
        "supports_time": True,
        "supported_resolutions": ["1", "3", "5", "15", "30", "60", "240", "1D", "1W", "1M"],
        "symbols_types": [{"name": "股票", "value": "stock"}],
    }


def frame_to_udf_history(frame: KlineFrame | None) -> dict[str, Any]:
    """Convert a newest-first frame into the ascending UDF history payload."""
    if frame is None or not frame.bars:
        return {"s": "no_data"}

    bars = sorted(frame.bars, key=lambda bar: float(bar.ts_open))
    payload: dict[str, Any] = {
        "s": "ok",
        "t": [],
        "o": [],
        "h": [],
        "l": [],
        "c": [],
        "v": [],
    }
    for bar in bars:
        # UDF timestamps are whole seconds.  De-duplicate bars that collapse
        # to the same second after conversion, keeping the newest source bar.
        ts = int(float(bar.ts_open) / 1000)
        if payload["t"] and ts == payload["t"][-1]:
            for key, value in (("o", bar.open), ("h", bar.high), ("l", bar.low),
                               ("c", bar.close), ("v", bar.volume)):
                payload[key][-1] = float(value)
            continue
        payload["t"].append(ts)
        payload["o"].append(float(bar.open))
        payload["h"].append(float(bar.high))
        payload["l"].append(float(bar.low))
        payload["c"].append(float(bar.close))
        payload["v"].append(float(bar.volume))
    return payload if payload["t"] else {"s": "no_data"}


def frame_to_symbol_info(frame: KlineFrame | None, symbol: str) -> dict[str, Any]:
    """Return the symbol metadata expected by ``resolveSymbol``."""
    name = symbol or (frame.symbol if frame else "PA")
    return {
        "name": name,
        "ticker": name,
        "full_name": name,
        "description": name,
        "exchange": "PA",
        "listed_exchange": "PA",
        "type": "stock",
        "session": "0000-2400",
        "timezone": "Asia/Shanghai",
        "format": "price",
        "pricescale": 100,
        "minmov": 1,
        "has_intraday": True,
        "has_daily": True,
        "has_weekly_and_monthly": True,
        "supported_resolutions": udf_config()["supported_resolutions"],
        "data_status": "streaming",
        "volume_precision": 0,
    }


class UDFDatafeedServer:
    """Threaded localhost HTTP server exposing the latest PA Agent frame."""

    def __init__(
        self,
        frame_provider: Callable[[], KlineFrame | None],
        *,
        symbol_provider: Callable[[], list[str]] | None = None,
    ) -> None:
        self._frame_provider = frame_provider
        self._symbol_provider = symbol_provider or self._default_symbols
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        if self._server is None:
            return ""
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> str:
        if self._server is not None:
            return self.url
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                owner._handle(self)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="pa-udf", daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _handle(self, request: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(request.path)
        query = parse_qs(parsed.query)
        path = parsed.path.rstrip("/")
        frame = self._frame_provider()
        if path == "/config":
            body: Any = udf_config()
        elif path in {"/time", "/server_time"}:
            body = int(time.time())
        elif path == "/history":
            requested = (query.get("symbol") or [""])[0]
            body = frame_to_udf_history(frame if not requested or frame is None or requested == frame.symbol else None)
        elif path in {"/symbols", "/symbol_info"}:
            requested = (query.get("symbol") or [""])[0]
            body = frame_to_symbol_info(frame, requested)
        elif path == "/search":
            needle = (query.get("query") or [""])[0].lower()
            symbols = self._symbol_provider()
            body = [
                {"symbol": symbol, "full_name": symbol, "description": symbol,
                 "exchange": "PA", "ticker": symbol, "type": "stock"}
                for symbol in symbols if not needle or needle in symbol.lower()
            ]
        elif path == "/quotes":
            body = self._quotes(frame, query.get("symbols", [""])[0])
        else:
            self._write_json(request, {"s": "error", "errmsg": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self._write_json(request, body)

    @staticmethod
    def _quotes(frame: KlineFrame | None, symbols: str) -> dict[str, Any]:
        bar = frame.bars[0] if frame and frame.bars else None
        values = {
            "ch": float(bar.close - bar.open) if bar else 0.0,
            "chp": float((bar.close - bar.open) / bar.open * 100) if bar and bar.open else 0.0,
            "lp": float(bar.close) if bar else 0.0,
            "open_price": float(bar.open) if bar else 0.0,
            "high_price": float(bar.high) if bar else 0.0,
            "low_price": float(bar.low) if bar else 0.0,
            "volume": float(bar.volume) if bar else 0.0,
        }
        return {"s": "ok", "d": [{"n": symbol, "s": "ok", "v": values} for symbol in symbols.split(",") if symbol]}

    @staticmethod
    def _write_json(request: BaseHTTPRequestHandler, body: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Access-Control-Allow-Origin", "*")
        request.send_header("Content-Length", str(len(data)))
        request.end_headers()
        request.wfile.write(data)

    def _default_symbols(self) -> list[str]:
        frame = self._frame_provider()
        return [frame.symbol] if frame else []

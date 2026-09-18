"""自选股点选 A 股时，后台并行探测国内数据源连通性。

保持 UI 线程不阻塞：探测在 QThread 中执行，完成后经信号回到主线程。
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class AshareSourceProbeWorker(QThread):
    """Probe domestic A-share data sources off the UI thread.

    Emits ``result_ready(kind, detail)`` once; *kind* is the first connected
    domestic source in ``A_SHARE_SOURCE_KINDS`` priority order ("" when none).
    """

    result_ready = pyqtSignal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._timeout_s: float | None = None

    def set_timeout_s(self, timeout_s: float) -> None:
        self._timeout_s = timeout_s

    def run(self) -> None:
        try:
            from pa_agent.data.factory import first_connected_a_share_source

            if self.isInterruptionRequested():
                return
            timeout = self._timeout_s
            kwargs = {"timeout_s": timeout} if timeout is not None else {}
            kind = first_connected_a_share_source(**kwargs)
            if self.isInterruptionRequested():
                return
            self.result_ready.emit(kind or "", "")
        except Exception as exc:  # noqa: BLE001 — 探测失败即结果
            logger.warning("自选股数据源探测失败: %s", exc)
            self.result_ready.emit("", str(exc))

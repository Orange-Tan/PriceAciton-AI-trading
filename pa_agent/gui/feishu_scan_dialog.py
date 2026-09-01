"""飞书「扫码一键创建机器人并绑定」对话框.

点击后后台发起飞书设备授权注册（OAuth 2.0 Device Authorization Grant），
弹窗内展示二维码：用户用手机飞书扫一扫 → 确认 → 手机端自动创建带机器人能力
的应用并开通权限 → 本软件轮询到 App ID / App Secret 以及扫码用户的 open_id，
自动写入 settings.feishu 并刷新设置面板。之后下单信号经 ``im/v1/messages``
直接推送到手机飞书里「与机器人的单聊」，无需手动建群、无需 Webhook。

二维码渲染使用可选依赖 ``segno``（纯 Python，无 PIL）；未安装时降级为
可复制的链接 + 「在浏览器打开」按钮。
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pa_agent.config.settings import Settings
from pa_agent.gui.theme import tokens as T

logger = logging.getLogger(__name__)

_QR_SIZE = 300


def render_qr_pixmap(url: str, size: int = _QR_SIZE) -> QPixmap | None:
    """把 url 渲染成二维码 QPixmap；未安装 segno 时返回 None。"""
    try:
        import segno  # type: ignore[import]
    except ImportError:
        return None
    qr = segno.make(url, error="m")
    matrix = qr.matrix
    rows = len(matrix)
    if rows == 0:
        return None
    border = 4
    cell = max(1, (size - 8) // (rows + 2 * border))
    side = cell * (rows + 2 * border)
    img = QImage(side, side, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    painter = QPainter(img)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#111827"))
    for r, row in enumerate(matrix):
        for c, v in enumerate(row):
            if bool(v):
                painter.drawRect((c + border) * cell, (r + border) * cell, cell, cell)
    painter.end()
    return QPixmap.fromImage(img)


class FeishuScanWorker(QThread):
    """后台执行 begin + poll，不阻塞 GUI。"""

    qr_ready = pyqtSignal(str)  # verification_url
    status_changed = pyqtSignal(str)
    success = pyqtSignal(str, str, str, str, str)  # client_id, client_secret, open_id, name, brand
    failed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        from pa_agent.notify import feishu_scan

        try:
            info = feishu_scan.begin_registration()
        except Exception as exc:
            self.failed.emit(f"发起扫码注册失败：\n{exc}")
            return
        self.qr_ready.emit(info.verification_url)
        try:
            result = feishu_scan.poll_registration(
                info,
                stop_event=self._stop,
                on_status=self.status_changed.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if result is None:
            self.failed.emit("已取消绑定。")
            return
        self.success.emit(
            result.client_id,
            result.client_secret,
            result.open_id,
            result.name,
            result.tenant_brand,
        )


class FeishuScanDialog(QDialog):
    """展示二维码、跟踪轮询状态、成功后写入 settings.feishu。"""

    def __init__(
        self,
        settings: Settings,
        parent: QWidget | None = None,
        *,
        on_bound: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("扫码一键创建并绑定")
        self.setMinimumWidth(420)
        self._settings = settings
        self._on_bound = on_bound
        self._bound = False

        root = QVBoxLayout(self)
        root.setSpacing(10)

        self._qr_label = QLabel("正在生成二维码…")
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(_QR_SIZE, _QR_SIZE)
        root.addWidget(self._qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._status_label = QLabel("正在发起…")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(f"color: {T.FG_2};")
        root.addWidget(self._status_label)

        steps = QLabel(
            "1. 打开手机飞书，用「扫一扫」扫描上方二维码\n"
            "2. 手机上确认创建机器人（自动开通消息推送权限）\n"
            "3. 确认后本软件自动绑定，信号将推送到手机飞书的机器人单聊\n\n"
            "链接约 10 分钟内有效，仅限本人使用。"
        )
        steps.setWordWrap(True)
        steps.setStyleSheet(f"color: {T.FG_2}; font-size: 11px;")
        root.addWidget(steps)

        # 无 segno 时的降级输入行
        self._url_row = QWidget()
        url_layout = QHBoxLayout(self._url_row)
        url_layout.setContentsMargins(0, 0, 0, 0)
        self._url_edit = QLineEdit()
        self._url_edit.setReadOnly(True)
        self._url_edit.setPlaceholderText("未安装 segno，无法显示二维码，可手动打开以下链接")
        url_layout.addWidget(self._url_edit, stretch=1)
        self._copy_btn = QPushButton("复制链接")
        self._copy_btn.clicked.connect(self._copy_url)
        url_layout.addWidget(self._copy_btn)
        self._open_btn = QPushButton("在浏览器打开")
        self._open_btn.clicked.connect(self._open_url)
        url_layout.addWidget(self._open_btn)
        self._url_row.hide()
        root.addWidget(self._url_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._close_btn = QPushButton("取消")
        self._close_btn.clicked.connect(self._on_close_clicked)
        btn_row.addWidget(self._close_btn)
        root.addLayout(btn_row)

        self._worker = FeishuScanWorker(self)
        self._worker.qr_ready.connect(self._on_qr_ready)
        self._worker.status_changed.connect(self._status_label.setText)
        self._worker.success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    # ── 信号处理 ──────────────────────────────────────────────────────────────

    def _on_qr_ready(self, url: str) -> None:
        self._verification_url = url
        pm = render_qr_pixmap(url)
        if pm is None:
            self._url_edit.setText(url)
            self._url_row.show()
            self._qr_label.setText("未安装 segno，无法显示二维码")
        else:
            self._qr_label.setPixmap(pm)
        self._status_label.setText("等待手机扫码确认…")

    def _on_success(
        self,
        client_id: str,
        client_secret: str,
        open_id: str,
        name: str,
        brand: str,
    ) -> None:
        self._bound = True
        feishu = self._settings.feishu
        feishu.enabled = True
        feishu.app_id = client_id
        feishu.app_secret = client_secret
        feishu.bound_open_id = open_id
        feishu.bound_name = name
        feishu.bound_tenant_brand = brand or "feishu"
        try:
            from pa_agent.config.paths import SETTINGS_JSON_PATH
            from pa_agent.config.settings import save_settings

            save_settings(self._settings, SETTINGS_JSON_PATH)
        except Exception as exc:  # 落盘失败不阻断绑定，稍后点保存会再写
            logger.warning("飞书扫码绑定后落盘失败: %s", exc)

        who = name or open_id or "你的飞书账号"
        self._qr_label.setText("✅")
        self._status_label.setStyleSheet(f"color: {T.ACCENT_PRIMARY};")
        self._status_label.setText(f"绑定成功：{who}\n信号将推送到手机飞书的机器人单聊。")
        self._close_btn.setText("完成")
        if self._on_bound is not None:
            self._on_bound()

    def _on_failed(self, message: str) -> None:
        if self._bound:
            return
        self._status_label.setText(message)
        self._close_btn.setText("关闭")

    # ── 按钮 ──────────────────────────────────────────────────────────────────

    def _copy_url(self) -> None:
        url = getattr(self, "_verification_url", "")
        if url:
            QApplication.clipboard().setText(url)
            self._copy_btn.setText("已复制")

    def _open_url(self) -> None:
        url = getattr(self, "_verification_url", "")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_close_clicked(self) -> None:
        self.reject()

    def _shutdown_worker(self) -> None:
        """Detach a running scan thread before destroying the dialog."""
        worker = getattr(self, "_worker", None)
        if worker is None:
            return
        worker.stop()
        if not worker.isRunning():
            worker.deleteLater()
            self._worker = None
            return
        for signal in (
            worker.qr_ready,
            worker.status_changed,
            worker.success,
            worker.failed,
        ):
            try:
                signal.disconnect()
            except (TypeError, RuntimeError):
                pass
        worker.setParent(None)
        worker.finished.connect(worker.deleteLater)
        self._worker = None

    def reject(self) -> None:  # noqa: N802
        self._shutdown_worker()
        super().reject()

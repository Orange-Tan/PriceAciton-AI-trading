"""Dialog when TradingView cannot be reached (typical: no outbound internet)."""
from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

TV_CLOUD_SERVER_WIKI_URL = "https://my.feishu.cn/wiki/FuqnwkPwdiCLhQkPloKc7r1lntg"

_MESSAGE = (
    "当前设备无法连接外网，因此无法使用 TradingView 作为 K 线数据来源。\n\n"
    "建议在香港云服务器上部署并运行本程序，即可正常连接 TradingView 拉取行情。"
)


def open_tv_cloud_server_wiki() -> None:
    QDesktopServices.openUrl(QUrl(TV_CLOUD_SERVER_WIKI_URL))


def show_tv_connectivity_blocked_dialog(parent: QWidget | None = None) -> str:
    """Show blocking dialog. Returns ``mt5``, ``cloud``, or ``cancel``."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("无法使用 TradingView")
    dlg.setMinimumWidth(440)

    layout = QVBoxLayout(dlg)
    label = QLabel(_MESSAGE)
    label.setWordWrap(True)
    layout.addWidget(label)

    buttons = QHBoxLayout()
    buttons.addStretch()
    btn_mt5 = QPushButton("切换回 MT5")
    btn_cloud = QPushButton("使用云服务器")
    buttons.addWidget(btn_mt5)
    buttons.addWidget(btn_cloud)
    layout.addLayout(buttons)

    result: list[str] = ["cancel"]

    def _pick(choice: str) -> None:
        result[0] = choice
        dlg.accept()

    btn_mt5.clicked.connect(lambda: _pick("mt5"))
    btn_cloud.clicked.connect(
        lambda: (open_tv_cloud_server_wiki(), _pick("cloud"))
    )

    dlg.exec()
    return result[0]

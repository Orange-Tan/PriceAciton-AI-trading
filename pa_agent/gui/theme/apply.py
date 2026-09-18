"""Apply the global application theme (深灰 / 浅色)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QApplication

from pa_agent.gui.theme import tokens as T

#: 内置主题 kind（与 pa_agent/gui/theme/*.qss 一一对应）。
THEME_KINDS: tuple[str, ...] = ("dark_gray", "light")
_DEFAULT_KIND: str = "light"
_QSS_DIR = Path(__file__).parent


def _resolve_kind(kind: str | None) -> str:
    """校验 kind；None 时从 settings.json 读取上次保存的主题。"""
    if kind in THEME_KINDS:
        return kind
    try:
        from pa_agent.config.paths import SETTINGS_JSON_PATH
        from pa_agent.config.settings import load_settings

        saved = load_settings(SETTINGS_JSON_PATH).general.theme
        if saved in THEME_KINDS:
            return saved
    except Exception:  # noqa: BLE001 — 设置缺失/损坏时回退默认
        pass
    return _DEFAULT_KIND


def apply_theme(app: QApplication, kind: str | None = None) -> str:
    """应用主题 ``kind``（缺省从设置读取），返回实际生效的 kind。

    会同步切换 ``tokens`` 调色板，使运行期通过 ``T.*`` 取色的组件跟随。
    """
    kind = _resolve_kind(kind)
    T.set_active_theme(kind)
    qss_path = _QSS_DIR / f"{kind}.qss"
    if qss_path.is_file():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    app.setStyle("Fusion")
    return kind


def apply_theme_from_settings(settings: Any) -> str:
    """从 ``settings.general.theme`` 读取主题并全局应用，返回生效的 kind。

    供设置对话框保存时调用：主题变更后立即作用于所有窗口。
    """
    kind = getattr(settings.general, "theme", _DEFAULT_KIND) or _DEFAULT_KIND
    app = QApplication.instance()
    if app is None:
        return _resolve_kind(kind)
    return apply_theme(app, kind)

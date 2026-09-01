"""Design tokens for PA Agent — 两套主题（深灰 / 浅色）.

``tokens`` 模块通过模块级 ``__getattr__`` 把 ``T.XXX`` 解析为**当前激活主题**
的调色板颜色，因此 ``apply_theme()`` 切换主题后，任何在运行期通过 ``T.*``
取色的组件（决策树、决策路径可视化、图表等）都会立即跟随。

用法
----
.. code-block:: python

    from pa_agent.gui.theme import tokens as T
    from pa_agent.gui.theme import apply_theme
    apply_theme(app, "light")          # 先切主题
    color = T.ACCENT_PRIMARY           # 再取色 -> 浅色主题的蓝色

直接 ``from pa_agent.gui.theme.tokens import ACCENT_DANGER`` 也会经
``__getattr__`` 返回当前主题值。
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 三套主题调色板
# ---------------------------------------------------------------------------
_PALETTES: dict[str, dict[str, str]] = {
    # ── 深灰（默认）：与旧 dark.qss 一致 ──────────────────────────────────────
    "dark_gray": {
        "BG": "#0a0e14",
        "SURFACE_1": "#161b22",
        "SURFACE_2": "#1c2128",
        "SURFACE_3": "#21262d",
        "SURFACE_4": "#30363d",
        "FG": "#e6edf3",
        "FG_2": "#8b949e",
        "FG_3": "#6e7681",
        "ACCENT": "#2dd4bf",
        "ACCENT_2": "#f87171",
        "ACCENT_3": "#38bdf8",
        "SUCCESS": "#22c55e",
        "DANGER": "#ef4444",
        "WARNING": "#f59e0b",
        "INFO": "#38bdf8",
        "CHART_UP": "#22c55e",
        "CHART_DOWN": "#ef4444",
        "CHART_GRID": "#1c2128",
        "CHART_LINE": "#fbbf24",
        "CHART_LINE_2": "#7dd3fc",
        "CHART_LINE_3": "#fb923c",
        "CHART_BG": "#0d1117",
        "PILL_GREEN_TEXT": "#86efac",
        "PILL_GREEN_BORDER": "rgba(34,197,94,0.35)",
        "PILL_GREEN_BG": "rgba(34,197,94,0.10)",
        "PILL_AMBER_TEXT": "#fbbf24",
        "PILL_AMBER_BORDER": "rgba(245,158,11,0.35)",
        "PILL_AMBER_BG": "rgba(245,158,11,0.10)",
        "PILL_BLUE_TEXT": "#7dd3fc",
        "PILL_BLUE_BORDER": "rgba(56,189,248,0.35)",
        "PILL_BLUE_BG": "rgba(56,189,248,0.10)",
        "PILL_RED_TEXT": "#fca5a5",
        "PILL_RED_BORDER": "rgba(239,68,68,0.35)",
        "PILL_RED_BG": "rgba(239,68,68,0.10)",
        "PILL_CYAN_TEXT": "#5eead4",
        "PILL_CYAN_BORDER": "rgba(45,212,191,0.35)",
        "PILL_CYAN_BG": "rgba(45,212,191,0.10)",
        "FONT_UI": '"Segoe UI", "Microsoft YaHei UI", sans-serif',
        "FONT_MONO": '"JetBrains Mono", "Cascadia Mono", "Consolas", monospace',
        "RADIUS": "6",
        "SPACING": "8",
        # 顶栏齿轮图标 / 悬停底色
        "TOOLBAR_ICON": "#8b949e",
        "TOOLBAR_HOVER": "#21262d",
    },
    # ── 浅色：浅灰底 + 白色卡片 ────────────────────────────────────────────────
    "light": {
        "BG": "#f3f5f7",
        "SURFACE_1": "#ffffff",
        "SURFACE_2": "#eef1f4",
        "SURFACE_3": "#e3e7ec",
        "SURFACE_4": "#d1d6dd",
        "FG": "#1f2937",
        "FG_2": "#6b7280",
        "FG_3": "#9ca3af",
        "ACCENT": "#0d9488",
        "ACCENT_2": "#dc2626",
        "ACCENT_3": "#2563eb",
        "SUCCESS": "#16a34a",
        "DANGER": "#dc2626",
        "WARNING": "#d97706",
        "INFO": "#2563eb",
        "CHART_UP": "#16a34a",
        "CHART_DOWN": "#dc2626",
        "CHART_GRID": "#e3e7ec",
        "CHART_LINE": "#d97706",
        "CHART_LINE_2": "#2563eb",
        "CHART_LINE_3": "#ea580c",
        "CHART_BG": "#ffffff",
        "PILL_GREEN_TEXT": "#15803d",
        "PILL_GREEN_BORDER": "rgba(22,163,74,0.35)",
        "PILL_GREEN_BG": "rgba(22,163,74,0.10)",
        "PILL_AMBER_TEXT": "#b45309",
        "PILL_AMBER_BORDER": "rgba(217,119,6,0.35)",
        "PILL_AMBER_BG": "rgba(217,119,6,0.10)",
        "PILL_BLUE_TEXT": "#1d4ed8",
        "PILL_BLUE_BORDER": "rgba(37,99,235,0.35)",
        "PILL_BLUE_BG": "rgba(37,99,235,0.10)",
        "PILL_RED_TEXT": "#b91c1c",
        "PILL_RED_BORDER": "rgba(220,38,38,0.35)",
        "PILL_RED_BG": "rgba(220,38,38,0.10)",
        "PILL_CYAN_TEXT": "#0f766e",
        "PILL_CYAN_BORDER": "rgba(13,148,136,0.35)",
        "PILL_CYAN_BG": "rgba(13,148,136,0.10)",
        "FONT_UI": '"Segoe UI", "Microsoft YaHei UI", sans-serif',
        "FONT_MONO": '"JetBrains Mono", "Cascadia Mono", "Consolas", monospace',
        "RADIUS": "6",
        "SPACING": "8",
        "TOOLBAR_ICON": "#4b5563",
        "TOOLBAR_HOVER": "#e2e8f0",
    },
}

#: 各主题的中文名（供设置界面展示）。
THEME_LABELS: dict[str, str] = {
    "dark_gray": "深灰",
    "light": "浅色",
}

_ACTIVE: str = "light"


def active_theme() -> str:
    """当前激活的主题 kind（dark_gray / light）。"""
    return _ACTIVE


def set_active_theme(kind: str) -> None:
    """切换当前激活主题；非法值保持原主题不变。"""
    global _ACTIVE
    if kind in _PALETTES:
        _ACTIVE = kind


def __getattr__(name: str) -> Any:
    """把 ``T.XXX`` 解析为当前主题调色板中的颜色值。

    保留旧版模块级常量的语义（如 ``BG_BASE``、``TEXT_PRIMARY`` 等别名）。
    """
    pal = _PALETTES[_ACTIVE]
    if name in pal:
        return pal[name]

    # Legacy aliases（旧命名 -> 新调色板键）
    _ALIASES: dict[str, str] = {
        "BG_BASE": "BG",
        "BG_PANEL": "SURFACE_1",
        "BG_ELEVATED": "SURFACE_2",
        "BG_REASONING": "SURFACE_2",
        "BG_INPUT": "BG",
        "BORDER": "SURFACE_4",
        "BORDER_MUTED": "SURFACE_3",
        "TEXT_PRIMARY": "FG",
        "TEXT_SECONDARY": "FG_2",
        "TEXT_MUTED": "FG_3",
        "ACCENT_PRIMARY": "ACCENT_3",
        "ACCENT_REASONING": "ACCENT",
        "ACCENT_SUCCESS": "SUCCESS",
        "ACCENT_WARNING": "WARNING",
        "ACCENT_DANGER": "DANGER",
        "TRADE_LONG": "CHART_UP",
        "TRADE_SHORT": "CHART_DOWN",
        "TRADE_NEUTRAL": "FG_2",
        "TOKEN_YELLOW": "WARNING",
        "TOKEN_RED": "DANGER",
    }
    if name in _ALIASES:
        return pal[_ALIASES[name]]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

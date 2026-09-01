"""右上角「设置」对话框 — 左右栏布局。

左侧为模块栏（数据源 / 模型 API / 飞书通知 / 交易决策 / 分析行为 /
图表与界面 / 决策树可视化），右侧显示选中模块的内容。

1. **数据源**：自由切换全部 6 种行情来源，并逐条说明「支持哪些行情」与
   「连通条件」。
2. **模型 API**：OpenAI 与国内头部 5 家厂商的配置与切换，同一厂商内可切换
   模型型号。
3. **飞书通知**：Webhook / 签名 / 自建应用配置与测试。
4. **交易决策 / 分析行为 / 图表与界面 / 决策树可视化**：原「通用设置」的
   四组选项直接提升到左侧模块栏，去掉「通用设置」这一层，各组分开显示。
   其中「图表与界面 → 界面风格」可切换软件的深灰 / 浅色显示风格。

对话框跟随全局显示风格，保存时若界面风格被修改会立即对所有界面生效。

对话框只负责把选择写回 ``settings`` 并落盘；真正的数据源切换由 MainWindow
在 ``exec()`` 返回后调用 ``_select_data_source_kind`` 完成。
"""
from __future__ import annotations

import math
import time
import logging
from collections.abc import Callable

from PyQt6.QtCore import QPointF, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pa_agent.config.model_providers import (
    PROVIDERS,
    find_provider,
    guess_provider,
)
from pa_agent.config.settings import Settings, save_settings
from pa_agent.config.paths import SETTINGS_JSON_PATH
from pa_agent.data.factory import normalize_data_source_kind
from pa_agent.gui.feishu_settings_dialog import FeishuSettingsPanel
from pa_agent.gui.general_settings_dialog import GeneralSettingsPanel
from pa_agent.gui.theme import tokens as T
from pa_agent.gui.theme.apply import apply_theme, apply_theme_from_settings

logger = logging.getLogger(__name__)

_CUSTOM_ID = "__custom__"

#: 左侧模块栏行号。
_MODULE_DS = 0
_MODULE_MODEL = 1
_MODULE_FEISHU = 2
#: 通用设置各分组从该行起（与 GeneralSettingsPanel.SECTION_TITLES 顺序一致）。
_MODULE_GENERAL_START = 3

#: 数据源说明（供「数据源」页签展示）。
DATA_SOURCE_INFO: dict[str, dict[str, str]] = {
    "tradingview": {
        "label": "TradingView",
        "markets": "全球外汇、贵金属（黄金/白银）、A股、港股、美股、全球指数、商品期货、加密货币",
        "connect": (
            "需联网；通过 tvDatafeed 匿名接口拉取，可能被墙或限流。"
            "首次「获取数据」前会自动做连通性探测，失败可一键切到腾讯财经。"
        ),
    },
    "akshare": {
        "label": "AkShare（A股）",
        "markets": "A股（沪/深）、A股指数；免费，无需券商账号",
        "connect": (
            "需联网访问东方财富/新浪等国内公开接口；免费额度有限、请求间隔约 0.9s；"
            "分钟线主要支持 1h 及以上周期。"
        ),
    },
    "eastmoney": {
        "label": "东方财富（A股）",
        "markets": "A股（沪/深）、A股指数",
        "connect": "需联网；程序内置 HTTP 接口，无需额外 token；部分分钟级历史数据用 Baostock 兜底。",
    },
    "tushare": {
        "label": "Tushare（A股）",
        "markets": "A股、指数、基金等专业数据",
        "connect": "需在 config/settings.json 的 tushare.token 填写 Tushare Pro token（需一定积分才可调用）。",
    },
    "tdx": {
        "label": "通达信（A股）",
        "markets": "A股（沪/深）、A股指数；免费，无需 token",
        "connect": (
            "需联网；通过 pytdx 协议直连通达信公开行情主站（多主站自动切换）。"
            "个股成交量按「股」、指数按原值；1m/5m/15m/30m/1h/4h/日/周/月 全周期。"
        ),
    },
    "tencent": {
        "label": "腾讯财经（A股）",
        "markets": "A股（沪/深）、A股指数；免费，无需 token",
        "connect": (
            "需联网；纯 HTTP 公开行情接口（前复权）。"
            "1m/5m/15m/30m/1h/4h/日/周/月 全周期。"
        ),
    },
}


def make_gear_icon(size: int = 20, color: str = "#8b949e") -> QIcon:
    """Draw a gear glyph into a QIcon (no external image asset needed)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    cx = cy = size / 2.0
    n = 8
    r_tooth_out = size * 0.48
    r_ring_out = size * 0.40
    r_ring_in = size * 0.28
    r_hub = size * 0.09

    # Teeth — thick radial strokes.
    painter.setPen(
        QPen(c, size * 0.16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
    )
    for i in range(n):
        ang = i * (2 * math.pi / n) - math.pi / 2
        x1 = cx + r_ring_in * math.cos(ang)
        y1 = cy + r_ring_in * math.sin(ang)
        x2 = cx + r_tooth_out * math.cos(ang)
        y2 = cy + r_tooth_out * math.sin(ang)
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    # Outer ring.
    painter.setPen(QPen(c, size * 0.12))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(cx, cy), (r_ring_out + r_ring_in) / 2, (r_ring_out + r_ring_in) / 2)

    # Hub.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(c))
    painter.drawEllipse(QPointF(cx, cy), r_hub, r_hub)

    painter.end()
    return QIcon(pm)


#: 探测结果缓存窗口：重开设置后“近期”（默认 30 分钟）连通成功的数据源仍显示绿灯。
_PROBE_RESULT_TTL_S = 30 * 60
#: {kind: (time.monotonic() 时间戳, ok, detail)} —— 跨对话框实例共享。
_PROBE_RESULTS: dict[str, tuple[float, bool, str]] = {}


def _status_icon(state: str) -> QIcon:
    """数据源状态小圆点：ok=绿 / fail=红 / busy=黄 / idle=灰。"""
    color = {
        "ok": "#3fb950",
        "fail": "#f85149",
        "busy": "#e6b800",
        "idle": "#8b949e",
    }[state]
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(3, 3, 10, 10)
    painter.end()
    return QIcon(pm)


class _DataSourceProbeWorker(QThread):
    """后台依次探测各数据源连通性，逐个上报结果。"""

    probed = pyqtSignal(str, bool, str)  # kind, ok, detail
    finished_all = pyqtSignal()

    def __init__(self, kinds: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kinds = list(kinds)

    def run(self) -> None:  # noqa: D102
        from pa_agent.data.factory import probe_data_source

        for kind in self._kinds:
            if self.isInterruptionRequested():
                return
            ok, detail = probe_data_source(kind)
            self.probed.emit(kind, ok, detail)
            if self.isInterruptionRequested():
                return
        self.finished_all.emit()


class AppSettingsDialog(QDialog):
    """统一设置对话框：数据源 + 模型 API + 飞书通知 + 通用设置四组。"""

    def __init__(
        self,
        settings: Settings,
        parent: QWidget | None = None,
        *,
        current_data_source_kind: str = "tradingview",
        decision_flow_play_handler: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(760, 520)
        self._settings = settings
        self._decision_flow_play_handler = decision_flow_play_handler
        # 打开对话框时已生效的主题：取消时回滚界面风格预览用
        self._theme_on_open = getattr(settings.general, "theme", "light") or "light"
        self.selected_data_source_kind = normalize_data_source_kind(current_data_source_kind)
        # 本次打开设置内的数据源连通检测结果：{kind: (ok, detail)}
        self._ds_probe_status: dict[str, tuple[bool, str]] = {}
        self._ds_probe_worker: _DataSourceProbeWorker | None = None
        self._setup_ui()
        self._load_values()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        body = QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)

        # 左侧：模块栏（数据源 / 模型 API / 飞书通知 + 通用设置四组直接提升上来）
        self._module_list = QListWidget()
        self._module_list.setFixedWidth(150)
        for title in ("数据源", "模型 API", "飞书通知") + GeneralSettingsPanel.SECTION_TITLES:
            self._module_list.addItem(title)
        self._module_list.currentRowChanged.connect(self._on_module_changed)
        body.addWidget(self._module_list)

        # 右侧：模块内容
        self._stack = QStackedWidget()

        # 模块 1: 数据源
        self._ds_list = QListWidget()
        self._ds_list.setFixedWidth(210)
        for kind in DATA_SOURCE_INFO:
            item = QListWidgetItem(DATA_SOURCE_INFO[kind]["label"])
            item.setData(Qt.ItemDataRole.UserRole, kind)
            item.setIcon(_status_icon("idle"))
            self._ds_list.addItem(item)
        self._ds_list.currentItemChanged.connect(self._on_data_source_selected)

        self._ds_info = QLabel("")
        self._ds_info.setWordWrap(True)
        self._ds_info.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._ds_info.setStyleSheet(f"color: {T.FG_2}; font-size: 12px;")

        # 当前选中数据源的连通检测结果
        self._ds_probe_label = QLabel("")
        self._ds_probe_label.setWordWrap(True)
        self._ds_probe_label.setStyleSheet(f"color: {T.FG_2}; font-size: 12px;")

        self._ds_probe_btn = QPushButton("检测当前数据源连通")
        self._ds_probe_btn.clicked.connect(self._probe_current_source)

        ds_right = QWidget()
        ds_right_layout = QVBoxLayout(ds_right)
        ds_right_layout.setContentsMargins(0, 0, 0, 0)
        ds_right_layout.setSpacing(6)
        ds_right_layout.addWidget(self._ds_info, stretch=1)
        ds_right_layout.addWidget(self._ds_probe_label)
        ds_right_layout.addWidget(
            self._ds_probe_btn, alignment=Qt.AlignmentFlag.AlignLeft
        )

        ds_widget = QWidget()
        ds_layout = QVBoxLayout(ds_widget)
        ds_layout.setContentsMargins(0, 0, 0, 0)
        ds_layout.setSpacing(6)

        # 一键检测全部
        probe_all_row = QHBoxLayout()
        self._ds_probe_all_btn = QPushButton("一键检测全部数据源")
        self._ds_probe_all_btn.clicked.connect(self._probe_all_sources)
        probe_all_hint = QLabel("绿灯＝连通正常（检测结果仅在本次打开设置内有效）")
        probe_all_hint.setStyleSheet(f"color: {T.FG_3}; font-size: 11px;")
        probe_all_row.addWidget(self._ds_probe_all_btn)
        probe_all_row.addWidget(probe_all_hint, stretch=1)
        ds_layout.addLayout(probe_all_row)

        ds_main_row = QHBoxLayout()
        ds_main_row.setContentsMargins(0, 0, 0, 0)
        ds_main_row.addWidget(self._ds_list)
        ds_main_row.addWidget(ds_right, stretch=1)
        ds_layout.addLayout(ds_main_row, stretch=1)
        self._stack.addWidget(ds_widget)

        # 模块 2: 模型 API
        self._stack.addWidget(self._build_model_tab())

        # 模块 3: 飞书通知
        self._feishu_panel = FeishuSettingsPanel(self._settings)
        self._feishu_scroll = QScrollArea()
        self._feishu_scroll.setWidgetResizable(True)
        self._feishu_scroll.setWidget(self._feishu_panel)
        self._stack.addWidget(self._feishu_scroll)

        # 通用设置：四组选项作为独立模块加入（对应 _MODULE_GENERAL_START 起的行号）
        self._general_panel = GeneralSettingsPanel(self._settings)
        self._general_panel.set_decision_flow_play_handler(
            self._decision_flow_play_handler
        )
        for page in self._general_panel.pages():
            self._stack.addWidget(page)

        body.addWidget(self._stack, stretch=1)
        root.addLayout(body)

        self._module_list.setCurrentRow(_MODULE_DS)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("保存")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText("取消")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_model_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("模型提供商")
        form = QFormLayout(group)

        self._provider_combo = QComboBox()
        for preset in PROVIDERS:
            self._provider_combo.addItem(preset.name, preset.id)
        self._provider_combo.addItem("自定义（手动填写 Base URL 与模型）", _CUSTOM_ID)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("提供商:", self._provider_combo)

        self._base_url_edit = QLineEdit()
        self._base_url_edit.setPlaceholderText("如 https://api.deepseek.com")
        form.addRow("Base URL:", self._base_url_edit)

        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._model_combo.setToolTip("可从下拉选择该厂商的型号，也可直接输入自定义模型名")
        form.addRow("模型:", self._model_combo)

        api_key_row = QHBoxLayout()
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self._api_key_edit.setPlaceholderText("输入 API Key")
        api_key_row.addWidget(self._api_key_edit)
        self._show_key_btn = QPushButton("隐藏")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setFixedWidth(52)
        self._show_key_btn.toggled.connect(self._toggle_api_key_visibility)
        api_key_row.addWidget(self._show_key_btn)
        form.addRow("API Key:", api_key_row)

        self._thinking_check = QCheckBox("启用 Thinking（部分模型不支持，需关闭）")
        form.addRow("Thinking:", self._thinking_check)

        self._reasoning_effort_combo = QComboBox()
        self._reasoning_effort_combo.addItems(["low", "medium", "high", "max"])
        form.addRow("Reasoning Effort:", self._reasoning_effort_combo)

        self._hint_label = QLabel("")
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet(f"color: {T.FG_2}; font-size: 11px;")
        form.addRow("", self._hint_label)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    # ── 加载 ───────────────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        # 数据源：先恢复“近期”检测结果，再选中当前生效的来源
        self._restore_ds_status_from_cache()
        for i in range(self._ds_list.count()):
            item = self._ds_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.selected_data_source_kind:
                self._ds_list.setCurrentRow(i)
                break
        self._update_data_source_info(self.selected_data_source_kind)

        # 模型：按当前 base_url/model 反推提供商
        p = self._settings.provider
        pid = guess_provider(p.base_url, p.model)
        if pid is None:
            pid = _CUSTOM_ID
        idx = self._provider_combo.findData(pid)
        if idx < 0:
            idx = self._provider_combo.findData(_CUSTOM_ID)
        self._provider_combo.setCurrentIndex(idx)

        # 提供商预设会填充 base_url 与模型列表；随后用已保存值覆盖
        self._apply_provider_preset(pid)
        self._base_url_edit.setText(p.base_url)

        model = p.model or ""
        if model:
            mi = self._model_combo.findData(model)
            if mi < 0:
                self._model_combo.addItem(model, model)
            self._model_combo.setCurrentIndex(self._model_combo.findData(model))

        self._api_key_edit.setText(p.api_key)
        self._thinking_check.setChecked(p.thinking)
        ri = self._reasoning_effort_combo.findText(p.reasoning_effort)
        if ri >= 0:
            self._reasoning_effort_combo.setCurrentIndex(ri)

    # ── 模块栏 ─────────────────────────────────────────────────────────────────

    def _on_module_changed(self, row: int) -> None:
        if 0 <= row < self._stack.count():
            self._stack.setCurrentIndex(row)

    def select_module(self, row: int) -> None:
        self._module_list.setCurrentRow(row)

    # ── 数据源 ─────────────────────────────────────────────────────────────────

    def _on_data_source_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        kind = str(current.data(Qt.ItemDataRole.UserRole))
        self.selected_data_source_kind = kind
        self._update_data_source_info(kind)

    def _update_data_source_info(self, kind: str) -> None:
        info = DATA_SOURCE_INFO.get(kind)
        if info is None:
            self._ds_info.setText("")
            return
        self._ds_info.setText(
            f"<b style='color:{T.FG}'>{info['label']}</b><br><br>"
            f"<span style='color:{T.ACCENT_PRIMARY}'>支持行情：</span>{info['markets']}<br><br>"
            f"<span style='color:{T.ACCENT_PRIMARY}'>连通条件：</span>{info['connect']}"
        )
        # 切换到某数据源时，若有检测结果则回显
        result = self._ds_probe_status.get(kind)
        if result is not None:
            self._show_probe_detail(kind, result[0], result[1])

    # ── 数据源连通检测 ──────────────────────────────────────────────────────────

    def _current_ds_kind(self) -> str:
        item = self._ds_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _show_probe_detail(self, kind: str, ok: bool, detail: str) -> None:
        self._ds_probe_label.setText(detail)
        color = T.PILL_GREEN_TEXT if ok else "#f85149"
        self._ds_probe_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _set_ds_status(self, kind: str, ok: bool, detail: str) -> None:
        self._ds_probe_status[kind] = (ok, detail)
        _PROBE_RESULTS[kind] = (time.monotonic(), ok, detail)
        for i in range(self._ds_list.count()):
            item = self._ds_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == kind:
                item.setIcon(_status_icon("ok" if ok else "fail"))
                break
        if self._current_ds_kind() == kind:
            self._show_probe_detail(kind, ok, detail)

    def _set_ds_busy(self, kind: str) -> None:
        for i in range(self._ds_list.count()):
            item = self._ds_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == kind:
                item.setIcon(_status_icon("busy"))
                break

    def _restore_ds_status_from_cache(self) -> None:
        """重开设置对话框时恢复“近期”检测结果：成功的来源保持绿灯。"""
        now = time.monotonic()
        for i in range(self._ds_list.count()):
            item = self._ds_list.item(i)
            kind = str(item.data(Qt.ItemDataRole.UserRole) or "")
            cached = _PROBE_RESULTS.get(kind)
            if cached is None:
                continue
            ts, ok, detail = cached
            if now - ts <= _PROBE_RESULT_TTL_S:
                self._ds_probe_status[kind] = (ok, detail)
                item.setIcon(_status_icon("ok" if ok else "fail"))

    def _probe_current_source(self) -> None:
        kind = self._current_ds_kind()
        if kind:
            self._start_probe([kind])

    def _probe_all_sources(self) -> None:
        self._start_probe(list(DATA_SOURCE_INFO.keys()))

    def _start_probe(self, kinds: list[str]) -> None:
        if getattr(self, "_ds_probe_worker", None) is not None and self._ds_probe_worker.isRunning():
            return
        for kind in kinds:
            self._set_ds_busy(kind)
        self._ds_probe_btn.setEnabled(False)
        self._ds_probe_all_btn.setEnabled(False)
        self._ds_probe_label.setText("检测中…（每个来源约需几秒到 20 秒）")
        worker = _DataSourceProbeWorker(kinds, self)
        worker.probed.connect(self._on_probed)
        worker.finished_all.connect(self._on_probe_all_done)
        self._ds_probe_worker = worker
        worker.start()

    def _on_probed(self, kind: str, ok: bool, detail: str) -> None:
        self._set_ds_status(kind, ok, detail)

    def _on_probe_all_done(self) -> None:
        self._ds_probe_btn.setEnabled(True)
        self._ds_probe_all_btn.setEnabled(True)
        total = len(self._ds_probe_status)
        ok_count = sum(1 for ok, _ in self._ds_probe_status.values() if ok)
        if total:
            self._ds_probe_label.setText(f"检测完成：{ok_count}/{total} 个数据源连通正常")

    def _shutdown_probe_worker(self) -> None:
        worker = getattr(self, "_ds_probe_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            # Never block the GUI thread while a third-party socket is stuck.
            # Detach signals and let the QThread clean itself up asynchronously.
            for signal, slot in (
                (worker.probed, self._on_probed),
                (worker.finished_all, self._on_probe_all_done),
            ):
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
            worker.setParent(None)
            worker.finished.connect(worker.deleteLater)
            self._ds_probe_worker = None

    def closeEvent(self, event) -> None:  # noqa: N802
        self._shutdown_probe_worker()
        super().closeEvent(event)

    # ── 模型 ───────────────────────────────────────────────────────────────────

    def _on_provider_changed(self, _index: int) -> None:
        pid = self._provider_combo.currentData()
        self._apply_provider_preset(pid)

    def _apply_provider_preset(self, pid: str | None) -> None:
        preset = find_provider(pid)
        if preset is None:
            # 自定义：保留当前字段，仅更新提示
            self._hint_label.setText("自定义提供商：请自行填写 Base URL、模型与 API Key。")
            return
        self._base_url_edit.setText(preset.base_url)
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for model_id, desc in preset.models:
            self._model_combo.addItem(f"{model_id}  ·  {desc}", model_id)
        self._model_combo.setCurrentIndex(0)
        self._model_combo.blockSignals(False)
        self._thinking_check.setChecked(preset.thinking_default)
        self._hint_label.setText(f"{preset.name}：获取 API Key → {preset.api_key_url}")

    def _toggle_api_key_visibility(self, checked: bool) -> None:
        if checked:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("显示")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("隐藏")

    # ── 保存 ───────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        p = self._settings.provider
        model = self._model_combo.currentData() or ""
        if not model:
            model = self._model_combo.currentText().strip()
        base_url = self._base_url_edit.text().strip()
        api_key = self._api_key_edit.text().strip()

        if not model:
            QMessageBox.warning(self, "模型 API 配置有误", "请填写模型名称。")
            return
        if base_url and not base_url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "模型 API 配置有误", "Base URL 需为 http(s) 地址。")
            return

        # 模型 API 与通用设置（含界面风格）先写回并应用，保证主题切换不被飞书校验阻塞。
        p.model = model
        p.base_url = base_url
        p.api_key = api_key
        p.thinking = self._thinking_check.isChecked()
        p.reasoning_effort = self._reasoning_effort_combo.currentText()  # type: ignore[assignment]

        self._general_panel.apply_values()
        apply_theme_from_settings(self._settings)

        item = self._ds_list.currentItem()
        if item is not None:
            self.selected_data_source_kind = normalize_data_source_kind(
                str(item.data(Qt.ItemDataRole.UserRole))
            )

        # 飞书通知：直接写回（未配置时静默保存，不弹框打断保存流程）。
        self._feishu_panel.apply_values()

        save_settings(self._settings, SETTINGS_JSON_PATH)
        self.accept()

    def reject(self) -> None:  # noqa: N802
        """取消时回滚界面风格预览（未点保存的主题不留在界面上）。"""
        from PyQt6.QtWidgets import QApplication

        self._shutdown_probe_worker()
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self._theme_on_open)
        super().reject()

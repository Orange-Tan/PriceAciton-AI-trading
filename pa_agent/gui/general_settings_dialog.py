"""通用设置 — 面板（产出四组通用设置页面）+ 独立对话框.

面板只负责构建「交易决策 / 分析行为 / 图表与界面 / 决策树可视化」四组
字段控件，不内置导航；导航由使用方（齿轮设置对话框的左侧模块栏，或独立
对话框自己的左右栏）安排，使各分组分开显示。
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pa_agent.config.paths import SETTINGS_JSON_PATH
from pa_agent.config.settings import Settings, save_settings
from pa_agent.gui.theme.apply import THEME_KINDS, apply_theme, apply_theme_from_settings
from pa_agent.gui.theme.tokens import THEME_LABELS


class GeneralSettingsPanel(QWidget):
    """通用设置表单的控件构建器（不含导航，供嵌入设置对话框复用）。

    四个分组各生成一个独立页面，由上层导航切换：

    - ``SECTION_TITLES``：四个分组的名称
    - ``pages()``：四个分组页面
    - ``sections()``：(名称, 页面) 成对序列
    """

    SECTION_TITLES: tuple[str, ...] = (
        "交易决策",
        "分析行为",
        "图表与界面",
        "决策树可视化",
    )
    demo_mode_requested = pyqtSignal(str)

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._decision_flow_play_handler: Callable[[], None] | None = None
        self.trade_page = self._build_trade_page()
        self.analysis_page = self._build_analysis_page()
        self.ui_page = self._build_ui_page()
        self.flow_page = self._build_flow_page()
        self.load_values()

    def pages(self) -> tuple[QWidget, ...]:
        """四个分组页面（与 SECTION_TITLES 一一对应）。"""
        return (self.trade_page, self.analysis_page, self.ui_page, self.flow_page)

    def sections(self) -> tuple[tuple[str, QWidget], ...]:
        return tuple(zip(self.SECTION_TITLES, self.pages()))

    # ── 页面构建辅助 ──────────────────────────────────────────────────────────

    @staticmethod
    def _form_group(title: str) -> tuple[QGroupBox, QFormLayout]:
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        return group, form

    @staticmethod
    def _page(group: QGroupBox) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(group)
        layout.addStretch()
        return page

    # ── 交易决策 ──────────────────────────────────────────────────────────────
    def _build_trade_page(self) -> QWidget:
        group, form = self._form_group("交易决策")

        self._decision_conf_threshold_spin = QSpinBox()
        self._decision_conf_threshold_spin.setRange(0, 100)
        self._decision_conf_threshold_spin.setToolTip(
            "当阶段二 trade_confidence 低于此阈值时，即使 AI 输出了限价单/突破单/市价单，\n"
            "也不视为下单机会（不弹窗警报、决策页按「不下单」处理）。设为 0 可关闭此门槛。"
        )
        form.addRow("下单置信度门槛:", self._decision_conf_threshold_spin)

        self._decision_stance_combo = QComboBox()
        self._decision_stance_combo.addItem("保守", "conservative")
        self._decision_stance_combo.addItem("均衡（默认，比保守更愿意下单）", "balanced")
        self._decision_stance_combo.addItem("激进（比均衡更愿意下单）", "aggressive")
        self._decision_stance_combo.addItem(
            "极度激进（强制选方向与进场方式）", "extreme_aggressive"
        )
        self._decision_stance_combo.setToolTip(
            "仅影响阶段二交易决策倾向；保守与改版前一致。\n"
            "均衡、激进逐级提高下单意愿；极度激进在未触犯 §14 硬性禁止时\n"
            "必须给出具体做多/做空及限价/突破/市价方案。"
        )
        form.addRow("交易倾向:", self._decision_stance_combo)

        self._alert_on_order_check = QCheckBox(
            "有下单机会时发出警报音和弹窗，并自动跳转到「决策」页"
        )
        self._alert_on_order_check.stateChanged.connect(self._on_alert_on_order_changed)
        form.addRow("下单提醒:", self._alert_on_order_check)

        self._enable_next_bar_check = QCheckBox("开启后在「未来走势预期」中显示下根K线预期")
        self._enable_next_bar_check.setToolTip(
            "开启后，AI 会在每次分析中额外预测下一根K线方向。关闭后不消耗额外 token。"
        )
        self._enable_next_bar_check.stateChanged.connect(self._on_enable_next_bar_changed)
        form.addRow("下根K线预期:", self._enable_next_bar_check)

        return self._page(group)

    # ── 分析行为 ──────────────────────────────────────────────────────────────
    def _build_analysis_page(self) -> QWidget:
        group, form = self._form_group("分析行为")

        self._analysis_bar_count_spin = QSpinBox()
        self._analysis_bar_count_spin.setRange(2, 5_000)
        self._analysis_bar_count_spin.setToolTip(
            "提交 AI 分析时使用的已收盘 K 线根数（不含当前未收盘 K 线）。"
        )
        form.addRow("用于分析的 K 线数量:", self._analysis_bar_count_spin)

        self._incremental_max_new_bars_spin = QSpinBox()
        self._incremental_max_new_bars_spin.setRange(0, 500)
        self._incremental_max_new_bars_spin.setSuffix(" 根")
        self._incremental_max_new_bars_spin.setToolTip(
            "同品种同周期下，若相对上一条成功记录只新增不超过该数量的已收盘K线，\n"
            "提交分析时走增量分析；设为 0 可关闭增量分析。"
        )
        form.addRow("增量分析最大新增K线:", self._incremental_max_new_bars_spin)

        self._keep_analysis_check = QCheckBox("有新K线收盘时自动开始新一轮分析")
        self._keep_analysis_check.setToolTip(
            "勾选后，每当有新的K线收盘时自动触发分析（与主界面「持续跟踪分析」勾选框同步）"
        )
        form.addRow("持续跟踪分析:", self._keep_analysis_check)

        self._cancel_keep_on_retry_check = QCheckBox("重试后取消持续跟踪分析")
        self._cancel_keep_on_retry_check.setToolTip(
            "勾选后，当 AI 输出触发校验重试时，自动关闭「持续跟踪分析」开关。"
        )
        form.addRow("重试行为:", self._cancel_keep_on_retry_check)

        self._last_symbol_edit = QLineEdit()
        form.addRow("上次品种:", self._last_symbol_edit)

        self._last_timeframe_edit = QLineEdit()
        form.addRow("上次周期:", self._last_timeframe_edit)

        return self._page(group)

    # ── 图表与界面 ────────────────────────────────────────────────────────────
    def _build_ui_page(self) -> QWidget:
        group, form = self._form_group("图表与界面")

        self._theme_combo = QComboBox()
        for kind in THEME_KINDS:
            self._theme_combo.addItem(THEME_LABELS.get(kind, kind), kind)
        self._theme_combo.setToolTip(
            "切换软件整体显示风格：深灰 / 浅色。\n选择后立即预览，点「保存」永久生效。"
        )
        self._theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        form.addRow("界面风格:", self._theme_combo)

        self._refresh_interval_spin = QSpinBox()
        self._refresh_interval_spin.setRange(100, 10_000)
        self._refresh_interval_spin.setSuffix(" ms")
        form.addRow("刷新间隔:", self._refresh_interval_spin)

        self._auto_resume_chart_check = QCheckBox("分析完成后自动恢复「图表实时更新」")
        form.addRow("图表:", self._auto_resume_chart_check)

        self._context_warning_spin = QSpinBox()
        self._context_warning_spin.setRange(1, 100)
        self._context_warning_spin.setSuffix(" %")
        form.addRow("上下文警告阈值:", self._context_warning_spin)

        self._stream_font_spin = QSpinBox()
        self._stream_font_spin.setRange(8, 28)
        self._stream_font_spin.setSuffix(" pt")
        self._stream_font_spin.setToolTip("「实时」标签页思考/回答框及追问输入框的字体大小")
        form.addRow("实时窗口字号:", self._stream_font_spin)

        self._chart_seq_font_spin = QSpinBox()
        self._chart_seq_font_spin.setRange(6, 24)
        self._chart_seq_font_spin.setSuffix(" pt")
        self._chart_seq_font_spin.setToolTip("K 线图上 #1、#3… 序号标签的字体大小")
        form.addRow("图表K线序号字号:", self._chart_seq_font_spin)

        page = self._page(group)
        demo_group = QGroupBox("演示模式")
        demo_layout = QHBoxLayout(demo_group)
        manual_btn = QPushButton("手动选择记录…")
        manual_btn.setObjectName("demoManualButton")
        manual_btn.clicked.connect(lambda: self.demo_mode_requested.emit("manual"))
        auto_btn = QPushButton("自动随机记录")
        auto_btn.setObjectName("demoAutoButton")
        auto_btn.clicked.connect(lambda: self.demo_mode_requested.emit("auto"))
        exit_btn = QPushButton("退出演示模式")
        exit_btn.setObjectName("demoExitButton")
        exit_btn.clicked.connect(lambda: self.demo_mode_requested.emit("exit"))
        demo_layout.addWidget(manual_btn)
        demo_layout.addWidget(auto_btn)
        demo_layout.addWidget(exit_btn)
        layout = page.layout()
        if layout is not None:
            layout.insertWidget(layout.count() - 1, demo_group)
        return page

    # ── 决策树可视化 ──────────────────────────────────────────────────────────
    def _build_flow_page(self) -> QWidget:
        group, form = self._form_group("决策树可视化")

        self._flow_auto_play_check = QCheckBox("决策树可视化生成后自动播放路径")
        form.addRow("自动播放:", self._flow_auto_play_check)

        self._flow_play_seconds_spin = QSpinBox()
        self._flow_play_seconds_spin.setRange(3, 120)
        self._flow_play_seconds_spin.setSuffix(" 秒")
        form.addRow("播放时长:", self._flow_play_seconds_spin)

        self._flow_default_zoom_spin = QSpinBox()
        self._flow_default_zoom_spin.setRange(10, 9_999_999)
        self._flow_default_zoom_spin.setSuffix(" %")
        self._flow_default_zoom_spin.setToolTip(
            "相对「整图适配」视图：100% 与适配一致，500% 放大 5 倍"
        )
        form.addRow("默认缩放:", self._flow_default_zoom_spin)

        self._flow_play_now_btn = QPushButton("播放决策树可视化")
        self._flow_play_now_btn.clicked.connect(self._on_play_decision_flow_now)
        form.addRow("", self._flow_play_now_btn)

        return self._page(group)

    # ── 加载 / 应用 ────────────────────────────────────────────────────────────

    def load_values(self) -> None:
        g = self._settings.general
        theme = getattr(g, "theme", "light") or "light"
        ti = self._theme_combo.findData(theme)
        if ti >= 0:
            self._theme_combo.setCurrentIndex(ti)

        self._decision_conf_threshold_spin.setValue(
            int(getattr(g, "decision_confidence_threshold", 40))
        )
        stance = getattr(g, "decision_stance", "conservative")
        idx = self._decision_stance_combo.findData(stance)
        if idx >= 0:
            self._decision_stance_combo.setCurrentIndex(idx)
        self._alert_on_order_check.blockSignals(True)
        self._alert_on_order_check.setChecked(bool(getattr(g, "alert_on_order_opportunity", True)))
        self._alert_on_order_check.blockSignals(False)
        self._enable_next_bar_check.blockSignals(True)
        self._enable_next_bar_check.setChecked(
            bool(getattr(g, "enable_next_bar_prediction", False))
        )
        self._enable_next_bar_check.blockSignals(False)

        self._analysis_bar_count_spin.setValue(g.analysis_bar_count)
        self._incremental_max_new_bars_spin.setValue(
            int(getattr(g, "incremental_max_new_bars", 10))
        )
        self._keep_analysis_check.setChecked(bool(getattr(g, "keep_analysis", False)))
        self._cancel_keep_on_retry_check.setChecked(
            bool(getattr(g, "cancel_keep_analysis_on_retry", False))
        )
        self._last_symbol_edit.setText(g.last_symbol)
        self._last_timeframe_edit.setText(g.last_timeframe)

        self._refresh_interval_spin.setValue(g.refresh_interval_ms)
        self._auto_resume_chart_check.setChecked(
            bool(getattr(g, "auto_resume_chart_after_analysis", False))
        )
        self._context_warning_spin.setValue(int(g.context_warning_threshold_pct))
        self._stream_font_spin.setValue(int(getattr(g, "stream_pane_font_pt", 11)))
        self._chart_seq_font_spin.setValue(int(getattr(g, "chart_seq_label_font_pt", 11)))

        self._flow_auto_play_check.setChecked(getattr(g, "decision_flow_auto_play", False))
        self._flow_play_seconds_spin.setValue(getattr(g, "decision_flow_play_seconds", 50))
        self._flow_default_zoom_spin.setValue(
            int(getattr(g, "decision_flow_default_zoom_pct", 600))
        )

    def apply_values(self) -> None:
        """把当前表单值写回 settings.general（不落盘，由对话框统一保存）。"""
        g = self._settings.general
        g.theme = self._theme_combo.currentData()  # type: ignore[assignment]
        g.decision_confidence_threshold = self._decision_conf_threshold_spin.value()
        g.decision_stance = self._decision_stance_combo.currentData()  # type: ignore[assignment]
        g.alert_on_order_opportunity = self._alert_on_order_check.isChecked()
        g.enable_next_bar_prediction = self._enable_next_bar_check.isChecked()

        g.analysis_bar_count = self._analysis_bar_count_spin.value()
        g.incremental_max_new_bars = self._incremental_max_new_bars_spin.value()
        g.keep_analysis = self._keep_analysis_check.isChecked()
        g.cancel_keep_analysis_on_retry = self._cancel_keep_on_retry_check.isChecked()
        g.last_symbol = self._last_symbol_edit.text().strip()
        g.last_timeframe = self._last_timeframe_edit.text().strip()

        g.refresh_interval_ms = self._refresh_interval_spin.value()
        g.auto_resume_chart_after_analysis = self._auto_resume_chart_check.isChecked()
        g.context_warning_threshold_pct = float(self._context_warning_spin.value())
        g.stream_pane_font_pt = self._stream_font_spin.value()
        g.chart_seq_label_font_pt = self._chart_seq_font_spin.value()

        g.decision_flow_auto_play = self._flow_auto_play_check.isChecked()
        g.decision_flow_play_seconds = self._flow_play_seconds_spin.value()
        g.decision_flow_default_zoom_pct = self._flow_default_zoom_spin.value()

    # ── 辅助 ──────────────────────────────────────────────────────────────────

    def _on_theme_selected(self, _index: int) -> None:
        """选择界面风格后立即全局预览切换（无需等待保存，取消会回滚）。"""
        from PyQt6.QtWidgets import QApplication

        kind = self._theme_combo.currentData()
        app = QApplication.instance()
        if app is not None and kind:
            apply_theme(app, kind)

    def set_decision_flow_play_handler(self, handler: Callable[[], None] | None) -> None:
        self._decision_flow_play_handler = handler

    def _on_alert_on_order_changed(self, _state: int) -> None:
        if not self._alert_on_order_check.isChecked():
            return
        from pa_agent.gui.order_opportunity import play_order_alert_sound

        play_order_alert_sound()

    def _on_enable_next_bar_changed(self, state: int) -> None:
        from PyQt6.QtCore import Qt as _Qt

        if state == _Qt.CheckState.Checked.value:
            from PyQt6.QtWidgets import QMessageBox as _MB

            _MB.information(
                self,
                "下根K线预期",
                "下根K线预期难度大，结果仅供参考。\n\nAI 预测单根K线方向的准确率有限，请勿将其作为交易依据。",
            )

    def _on_play_decision_flow_now(self) -> None:
        g = self._settings.general
        g.decision_flow_auto_play = self._flow_auto_play_check.isChecked()
        g.decision_flow_play_seconds = self._flow_play_seconds_spin.value()
        g.decision_flow_default_zoom_pct = self._flow_default_zoom_spin.value()
        if self._decision_flow_play_handler is not None:
            self._decision_flow_play_handler()


class GeneralSettingsDialog(QDialog):
    """通用设置对话框 — 左右栏（独立入口）。"""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("通用设置")
        self.setMinimumSize(680, 480)
        self._settings = settings
        # 打开对话框时已生效的主题：取消时回滚界面风格预览用
        self._theme_on_open = getattr(settings.general, "theme", "light") or "light"

        self._panel = GeneralSettingsPanel(settings, self)

        root = QVBoxLayout(self)

        body = QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)

        self._section_list = QListWidget()
        self._section_list.setFixedWidth(150)
        for title in self._panel.SECTION_TITLES:
            self._section_list.addItem(title)
        self._section_list.currentRowChanged.connect(self._on_section_changed)
        body.addWidget(self._section_list)

        self._stack = QStackedWidget()
        for page in self._panel.pages():
            self._stack.addWidget(page)
        body.addWidget(self._stack, stretch=1)

        root.addLayout(body)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
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

        self._section_list.setCurrentRow(0)

    def _on_section_changed(self, row: int) -> None:
        if 0 <= row < self._stack.count():
            self._stack.setCurrentIndex(row)

    def set_decision_flow_play_handler(self, handler: Callable[[], None] | None) -> None:
        self._panel.set_decision_flow_play_handler(handler)

    def _on_save(self) -> None:
        self._panel.apply_values()
        apply_theme_from_settings(self._settings)
        save_settings(self._settings, SETTINGS_JSON_PATH)
        self.accept()

    def reject(self) -> None:
        """取消时回滚界面风格预览（未点保存的主题不留在界面上）。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self._theme_on_open)
        super().reject()

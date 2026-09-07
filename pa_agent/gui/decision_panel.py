"""DecisionPanel — trading decision + market diagnosis summary."""
from __future__ import annotations

from PyQt6.QtCore import Qt

from pa_agent.util.trade_metrics import (
    compute_risk_reward,
    format_estimated_win_rate,
    max_risk_reward_ratio,
    min_risk_reward_ratio,
    passes_trader_equation,
)
from pa_agent.ai.cycle_enums import format_cycle_position, format_cycle_with_direction

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QProgressBar,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pa_agent.gui.future_trend_panel import FutureTrendPanel
from pa_agent.gui.theme import tokens as T

_NO_ORDER = "不下单"


# Reasoning text — larger than default mutedLabel (11px)；文字颜色跟随主题
def _reason_font_css() -> str:
    return f"font-size: 14px; color: {T.FG}; line-height: 1.45;"


def _reason_edit_css() -> str:
    return (
        f"font-size: 14px; color: {T.FG}; line-height: 1.45;"
        "font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;"
    )

_PREDICTION_UNPREDICTABLE_LABEL = "不可预测"

# 以震荡为主的周期类型
_RANGE_CYCLES = frozenset({"trading_range", "extreme_tr", "trending_tr"})

_MARKET_PHASE_ZH: dict[str, str] = {
    "stable": "稳定",
    "transitioning": "过渡",
}

_PREDICTION_DOMINANT_COLOR: dict[str, str] = {
    "bullish": "#3fb950",
    "bearish": "#f85149",
    "neutral": "#e6b800",
}


def _format_market_phase(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _MARKET_PHASE_ZH.get(key, raw or "—")


def _infer_trend_label(direction: str, cycle_position: str) -> str:
    """Map AI direction + cycle to 上涨 / 下跌 / 震荡."""
    cp = (cycle_position or "").strip().lower()
    d = (direction or "").strip().lower()

    if cp in _RANGE_CYCLES:
        return "震荡"

    if d == "bullish":
        return "上涨"
    if d == "bearish":
        return "下跌"
    if d == "neutral":
        return "震荡"

    if cp in ("spike", "micro_channel", "tight_channel"):
        return "趋势运行中"
    return "—"


def _trend_color(label: str) -> str:
    if label == "上涨":
        return "#3fb950"
    if label == "下跌":
        return "#f85149"
    if label in ("震荡", "趋势运行中"):
        return "#e6b800"
    return T.FG_2


def _score_color(score: int) -> str:
    if score >= 70:
        return "#3fb950"
    if score >= 50:
        return "#e6b800"
    return "#f85149"


def _parse_score_100(value: object) -> int | None:
    """Parse 0–100 confidence score."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    try:
        return max(0, min(100, int(float(str(value).strip()))))
    except (ValueError, TypeError):
        return None


def _format_prediction_probs_line(probs: dict) -> str:
    bull = probs.get("bullish", "?")
    bear = probs.get("bearish", "?")
    neut = probs.get("neutral", "?")
    return f"阳线的概率为{bull}%  ·  阴线的概率为{bear}%  ·  中性的概率为{neut}%"


def _dominant_prediction_direction(probs: dict) -> str | None:
    """Return bullish/bearish/neutral for styling by highest probability."""
    parsed: list[tuple[str, float]] = []
    for key in ("bullish", "bearish", "neutral"):
        raw = probs.get(key)
        if raw is None or raw == "":
            continue
        try:
            parsed.append((key, float(raw)))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return None
    return max(parsed, key=lambda item: item[1])[0]


class DecisionPanel(QWidget):
    """Renders market diagnosis + Stage-2 trading decision.

    Confidence layout (two bars):
      市场诊断区 → 市场判断置信度 (Stage 2 diagnosis_confidence)
      交易决策区 → 交易决策置信度 (Stage 2 trade_confidence, inline on summary row)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_decision: dict | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(10)

        self._title_label = QLabel("AI 交易决策")
        self._title_label.setObjectName("toolbarTitle")
        title_row_layout.addWidget(self._title_label)

        title_row_layout.addStretch(1)
        self._disclaimer_label = QLabel("分析仅供参考，不构成投资建议")
        self._disclaimer_label.setObjectName("mutedLabel")
        self._disclaimer_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._disclaimer_label.setWordWrap(False)
        self._disclaimer_label.setMinimumWidth(0)
        self._disclaimer_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        title_row_layout.addWidget(self._disclaimer_label)
        layout.addWidget(title_row)

        # 结论置顶，避免在“交易决策”区再次重复显示同一结论。
        self._conclusion_bar = QFrame()
        self._conclusion_bar.setObjectName("conclusionBar")
        conclusion_layout = QHBoxLayout(self._conclusion_bar)
        conclusion_layout.setContentsMargins(14, 10, 14, 10)
        conclusion_layout.setSpacing(10)

        self._conclusion_label = QLabel("等待分析")
        self._conclusion_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {T.FG_2};"
        )
        self._direction_inline_label = QLabel()
        self._direction_inline_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {T.FG_2};"
        )
        self._trade_conf_inline_label = QLabel()
        self._trade_conf_inline_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        conclusion_layout.addWidget(self._conclusion_label)
        conclusion_layout.addWidget(self._direction_inline_label)
        conclusion_layout.addStretch(1)
        conclusion_layout.addWidget(self._trade_conf_inline_label)
        layout.addWidget(self._conclusion_bar)

        # 市场诊断统一承载趋势、周期、阶段、支撑和阻力，替代独立摘要条。
        diag_title = QLabel("市场诊断")
        diag_title.setStyleSheet("font-weight: bold; color: #58a6ff;")
        layout.addWidget(diag_title)

        diag_grid = QWidget()
        diag_layout = QGridLayout(diag_grid)
        diag_layout.setContentsMargins(0, 0, 0, 0)
        diag_layout.setHorizontalSpacing(6)
        diag_layout.setVerticalSpacing(6)

        self._trend_label = QLabel("趋势：—")
        self._cycle_label = QLabel("周期：—")
        self._next_cycle_label = QLabel("下一周期：—")
        self._phase_label = QLabel("阶段：—")
        self._support_label = QLabel("支撑区：—")
        self._resistance_label = QLabel("阻力区：—")
        diag_labels = (
            self._trend_label,
            self._cycle_label,
            self._next_cycle_label,
            self._phase_label,
            self._support_label,
            self._resistance_label,
        )
        for idx, lbl in enumerate(diag_labels):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            diag_layout.addWidget(lbl, idx // 3, idx % 3)
        layout.addWidget(diag_grid)

        # ── 市场判断置信度（来自 Stage 2 diagnosis_confidence）───────────
        self._diag_conf_title = QLabel("市场判断置信度")
        self._diag_conf_title.setStyleSheet("font-weight: bold; margin-top: 6px;")
        layout.addWidget(self._diag_conf_title)

        self._diag_conf_bar = QProgressBar()
        self._diag_conf_bar.setRange(0, 100)
        self._diag_conf_bar.setTextVisible(True)
        self._diag_conf_bar.setFormat("%v / 100")
        self._diag_conf_bar.setMaximumHeight(22)
        layout.addWidget(self._diag_conf_bar)

        self._diag_conf_label = QLabel("—")
        layout.addWidget(self._diag_conf_label)

        self._diag_reasoning_label = QLabel()
        self._diag_reasoning_label.setWordWrap(True)
        self._diag_reasoning_label.setStyleSheet(_reason_font_css())
        layout.addWidget(self._diag_reasoning_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        # 交易参数只保留价格与统计，结论和交易置信度已在顶部展示。
        trade_title = QLabel("交易参数")
        trade_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(trade_title)

        self._rr_inline_label = QLabel("—")
        self._win_rate_inline_label = QLabel("—")

        self._trade_prices_row = QWidget()
        prices_layout = QHBoxLayout(self._trade_prices_row)
        prices_layout.setContentsMargins(0, 0, 0, 0)
        prices_layout.setSpacing(16)

        self._entry_label = QLabel("入场  —")
        self._tp_label = QLabel("TP1  —")
        self._tp2_label = QLabel("TP2  —")
        self._sl_label = QLabel("止损  —")
        for lbl in (self._entry_label, self._tp_label, self._tp2_label, self._sl_label):
            lbl.setStyleSheet(f"font-size: 14px; color: {T.FG};")
            prices_layout.addWidget(lbl, stretch=1)

        layout.addWidget(self._trade_prices_row)

        trade_stats_row = QWidget()
        trade_stats_layout = QHBoxLayout(trade_stats_row)
        trade_stats_layout.setContentsMargins(0, 2, 0, 0)
        trade_stats_layout.setSpacing(16)
        for lbl in (self._rr_inline_label, self._win_rate_inline_label):
            lbl.setStyleSheet(f"font-size: 13px; color: {T.FG_2};")
            trade_stats_layout.addWidget(lbl, stretch=1)
        layout.addWidget(trade_stats_row)

        self._trade_conf_title = QLabel("交易决策置信度")
        self._trade_conf_title.setStyleSheet("font-weight: bold; margin-top: 4px;")
        self._trade_conf_title.setVisible(False)

        self._trade_conf_bar = QProgressBar()
        self._trade_conf_bar.setRange(0, 100)
        self._trade_conf_bar.setTextVisible(True)
        self._trade_conf_bar.setFormat("%v / 100")
        self._trade_conf_bar.setMaximumHeight(22)
        self._trade_conf_bar.setVisible(False)

        self._trade_conf_label = QLabel()
        self._trade_conf_label.setVisible(False)

        self._trade_reasoning_label = QLabel()
        self._trade_reasoning_label.setWordWrap(True)
        self._trade_reasoning_label.setStyleSheet(_reason_font_css())

        # 说明支持展开/收起，默认全部展开，便于直接阅读完整决策依据。
        self._reasoning_edit = self._make_detail(layout, "分析理由", open=True)
        self._confidence_reasoning_edit = self._make_detail(layout, "置信度理由", open=True)
        self._risk_reasoning_edit = self._make_detail(
            layout, "风险评估与失效条件", open=True
        )

        future_title = QLabel("未来走势预期")
        future_title.setStyleSheet("font-weight: bold; color: #58a6ff; margin-top: 8px;")
        self._future_title_label = future_title
        layout.addWidget(future_title)
        self._future_trend_panel = FutureTrendPanel()
        self._future_trend_panel.set_embedded_mode(True)
        layout.addWidget(self._future_trend_panel)
        self._prediction_group = self._future_trend_panel._bar_group
        self._prediction_direction_label = self._future_trend_panel._bar_direction_label
        self._prediction_reasoning_edit = self._future_trend_panel._bar_reasoning_edit

        self.clear()

    def _make_detail(self, layout: QVBoxLayout, title: str, *, open: bool = False) -> QTextEdit:
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: bold; padding: 6px 0;")
        layout.addWidget(heading)

        edit = QTextEdit()
        edit.setReadOnly(True)
        edit.setObjectName("answerPane")
        edit.setStyleSheet(_reason_edit_css())
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        edit.setMinimumHeight(64)
        edit.setVisible(True)
        layout.addWidget(edit)
        return edit

    def _apply_diag_chip_style(self, label: QLabel, *, color: str) -> None:
        label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; padding: 8px 10px;"
            f"color: {color}; background-color: {T.SURFACE_3}; border-radius: 8px;"
        )

    def set_summary_metrics(self, metrics: dict[str, str]) -> None:
        """Update the consolidated diagnosis metrics shown in the panel."""
        mapping = {
            "当前趋势": self._trend_label,
            "当前市场周期": self._cycle_label,
            "下一个市场周期": self._next_cycle_label,
            "市场阶段": self._phase_label,
            "支撑区": self._support_label,
            "阻力区": self._resistance_label,
        }
        prefixes = {
            "当前趋势": "趋势：",
            "当前市场周期": "周期：",
            "下一个市场周期": "下一周期：",
            "市场阶段": "阶段：",
            "支撑区": "支撑区：",
            "阻力区": "阻力区：",
        }
        for key, label in mapping.items():
            if key in metrics:
                label.setText(f"{prefixes[key]}{metrics[key] or '—'}")

    def set_metrics(self, metrics: dict[str, str]) -> None:
        """Backward-compatible alias for callers that previously updated SummaryStrip."""
        self.set_summary_metrics(metrics)

    def reset_summary_metrics(self) -> None:
        self.set_summary_metrics(
            {
                "当前趋势": "—",
                "当前市场周期": "—",
                "下一个市场周期": "—",
                "市场阶段": "—",
                "支撑区": "—",
                "阻力区": "—",
            }
        )

    def reset(self) -> None:
        """Backward-compatible SummaryStrip reset hook."""
        self.reset_summary_metrics()

    # ── Data binding helpers ──────────────────────────────────────────────

    def _apply_market_diagnosis(
        self,
        diagnosis_summary: dict | None,
        stage1_diagnosis: dict | None = None,
    ) -> None:
        """Fill trend / cycle / phase from stage2 summary, fallback to stage1."""
        src: dict = {}
        if diagnosis_summary:
            src.update(diagnosis_summary)
        if stage1_diagnosis:
            for k, v in stage1_diagnosis.items():
                src.setdefault(k, v)

        direction = str(src.get("direction", "") or "")
        cycle_position = str(src.get("cycle_position", "") or "")
        alt_cycle = src.get("alternative_cycle_position")
        market_phase = str(src.get("market_phase", "") or "")

        trend = _infer_trend_label(direction, cycle_position)
        trend_color = _trend_color(trend)
        self._trend_label.setText(f"趋势：{trend}")
        self._apply_diag_chip_style(self._trend_label, color=trend_color)

        cycle_zh = format_cycle_with_direction(cycle_position, direction)
        cycle_text = f"周期：{cycle_zh}"
        if alt_cycle:
            cycle_text += f"（备选 {format_cycle_position(str(alt_cycle))}）"
        self._cycle_label.setText(cycle_text)
        self._apply_diag_chip_style(self._cycle_label, color=T.FG)

        if market_phase:
            phase_zh = _format_market_phase(market_phase)
            extra = ""
            risk = src.get("transition_risk")
            if market_phase == "transitioning" and risk:
                extra = f" · 风险 {risk}"
            self._phase_label.setText(f"阶段：{phase_zh}{extra}")
            self._phase_label.setVisible(True)
            phase_color = "#e6b800" if market_phase == "transitioning" else "#58a6ff"
            self._apply_diag_chip_style(self._phase_label, color=phase_color)
        else:
            self._phase_label.setText("阶段：—")
            self._apply_diag_chip_style(self._phase_label, color=T.FG_3)
            self._phase_label.setVisible(True)

    def _apply_diagnosis_confidence(
        self,
        diagnosis_confidence: object,
        diagnosis_confidence_reasoning: str | None,
    ) -> None:
        """Render market-judgment confidence bar (Stage 2 diagnosis_confidence)."""
        score = _parse_score_100(diagnosis_confidence)
        if score is not None:
            c_color = _score_color(score)
            self._diag_conf_bar.setValue(score)
            self._diag_conf_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {c_color}; }}"
            )
            self._diag_conf_label.setText(f"评分 {score} / 100")
            self._diag_conf_label.setStyleSheet(f"color: {c_color}; font-weight: bold;")
            reason_text = str(diagnosis_confidence_reasoning or "").strip()
            self._diag_reasoning_label.setText(
                f"理由：{reason_text}" if reason_text else ""
            )
            self._diag_conf_title.setVisible(True)
            self._diag_conf_bar.setVisible(True)
            self._diag_conf_label.setVisible(True)
            self._diag_reasoning_label.setVisible(bool(reason_text))
        else:
            self._diag_conf_bar.setValue(0)
            self._diag_conf_title.setVisible(False)
            self._diag_conf_bar.setVisible(False)
            self._diag_conf_label.setVisible(False)
            self._diag_reasoning_label.setVisible(False)

    def _apply_trade_confidence_inline(
        self,
        trade_confidence: object,
        trade_confidence_reasoning: str | None,
        *,
        no_order: bool = False,
    ) -> None:
        """Show trade confidence on the summary row; optional reasoning below."""
        score = _parse_score_100(trade_confidence)
        if score is not None:
            c_color = _score_color(score)
            hint = "观望" if no_order else "入场"
            self._trade_conf_inline_label.setText(
                f"置信度 {score} / 100 · {hint}"
            )
            self._trade_conf_inline_label.setStyleSheet(
                f"font-size: 15px; font-weight: bold; color: {c_color};"
            )
            self._trade_conf_inline_label.setVisible(True)
            reason_text = str(trade_confidence_reasoning or "").strip()
            self._trade_reasoning_label.setText(
                f"置信度理由：{reason_text}" if reason_text else ""
            )
            self._trade_reasoning_label.setVisible(bool(reason_text))
        else:
            self._trade_conf_inline_label.setText("")
            self._trade_conf_inline_label.setVisible(False)
            self._trade_reasoning_label.setVisible(False)

    def _set_conclusion_bar_style(self) -> None:
        self._conclusion_bar.setStyleSheet(
            f"QFrame#conclusionBar {{"
            f"  background-color: {T.SURFACE_3};"
            "  border-radius: 8px;"
            "}"
        )

    def _reset_conclusion_bar_side_labels(self) -> None:
        self._rr_inline_label.setText("—")
        self._win_rate_inline_label.setText("—")
        self._rr_inline_label.setVisible(False)
        self._win_rate_inline_label.setVisible(False)

    # ── Public API ────────────────────────────────────────────────────────

    def set_decision(
        self,
        decision: dict,
        *,
        diagnosis_summary: dict | None = None,
        stage1_diagnosis: dict | None = None,
        decision_stance: str | None = None,
        confidence_threshold: int | None = None,
    ) -> None:
        self._last_decision = {
            "decision": decision,
            "diagnosis_summary": diagnosis_summary,
            "stage1_diagnosis": stage1_diagnosis,
            "decision_stance": decision_stance,
            "confidence_threshold": confidence_threshold,
        }
        self._apply_market_diagnosis(diagnosis_summary, stage1_diagnosis)

        order_type = decision.get("order_type", _NO_ORDER)
        reasoning = decision.get("reasoning", decision.get("brief_reasoning", ""))
        # Confidence gate: suppress order display when confidence < threshold
        if confidence_threshold is not None and confidence_threshold > 0 and order_type != _NO_ORDER:
            raw_conf = decision.get("trade_confidence")
            try:
                conf_val = int(float(str(raw_conf).strip())) if raw_conf is not None and raw_conf != "" else -1
            except (ValueError, TypeError):
                conf_val = -1
            if conf_val < confidence_threshold:
                order_type = _NO_ORDER
                prefix = "有入场机会，但置信度未通过"
                reasoning = f"{prefix}\n\n{reasoning}" if reasoning else prefix
        diag_conf = decision.get("diagnosis_confidence", None)
        diag_conf_reasoning = decision.get("diagnosis_confidence_reasoning", None)
        trade_conf = decision.get("trade_confidence", None)
        trade_conf_reasoning = decision.get("trade_confidence_reasoning", None)

        self._apply_diagnosis_confidence(diag_conf, diag_conf_reasoning)

        if order_type == _NO_ORDER:
            self._reset_conclusion_bar_side_labels()
            self._conclusion_label.setText(_NO_ORDER)
            self._conclusion_label.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {T.FG_2};"
            )
            self._direction_inline_label.setText("")
            self._direction_inline_label.setVisible(False)
            self._trade_prices_row.setVisible(False)
            self._conclusion_bar.setVisible(True)
            self._set_conclusion_bar_style()
            self._apply_trade_confidence_inline(
                trade_conf, trade_conf_reasoning,
                no_order=True,
            )
        else:
            direction = decision.get("order_direction", "—")
            entry = decision.get("entry_price")
            tp = decision.get("take_profit_price")
            tp2 = decision.get("take_profit_price_2")
            sl = decision.get("stop_loss_price")

            self._conclusion_label.setText(str(order_type))
            color = "#3fb950" if "多" in str(direction) else "#f85149"
            self._conclusion_label.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {color};"
            )
            self._direction_inline_label.setText(f"方向 {direction}")
            self._direction_inline_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {color};"
            )
            self._direction_inline_label.setVisible(True)

            self._entry_label.setText(
                f"入场  {entry:.5g}" if entry is not None else "入场  —"
            )
            self._tp_label.setText(f"TP1  {tp:.5g}" if tp is not None else "TP1  —")
            self._tp2_label.setText(
                f"TP2  {tp2:.5g}" if tp2 is not None else "TP2  —"
            )
            self._sl_label.setText(f"止损  {sl:.5g}" if sl is not None else "止损  —")
            self._trade_prices_row.setVisible(True)

            self._conclusion_bar.setVisible(True)
            self._set_conclusion_bar_style()

            rr = compute_risk_reward(entry, tp, sl, direction)
            if rr is not None:
                ratio = float(rr["ratio"])
                risk = float(rr["risk"])
                reward = float(rr["reward"])
                win_pct = _parse_score_100(decision.get("estimated_win_rate"))
                eq_ok = (
                    win_pct is not None
                    and passes_trader_equation(win_pct, risk, reward)
                )
                min_rr = min_risk_reward_ratio(decision_stance)
                max_rr = max_risk_reward_ratio()
                metrics_ok = (
                    ratio >= min_rr
                    and (max_rr is None or ratio <= max_rr)
                    and (eq_ok if win_pct is not None else True)
                )
                eq_note = ""
                if win_pct is not None:
                    eq_note = " · 方程通过" if eq_ok else " · 方程不通过"
                self._rr_inline_label.setText(
                    f"盈亏比  {rr['ratio_text']}（风险 {risk:.4g} / 回报 {reward:.4g}）{eq_note}"
                )
                rr_color = "#3fb950" if metrics_ok else "#f85149"
                self._rr_inline_label.setStyleSheet(
                    f"color: {rr_color}; font-size: 15px; font-weight: bold;"
                )
                self._rr_inline_label.setVisible(True)
            else:
                self._rr_inline_label.setText("盈亏比  —（三价无效）")
                self._rr_inline_label.setStyleSheet(
                    "color: #f85149; font-size: 15px; font-weight: bold;"
                )
                self._rr_inline_label.setVisible(True)

            win_rate = format_estimated_win_rate(decision)
            if win_rate:
                self._win_rate_inline_label.setText(f"预估胜率  {win_rate}")
            else:
                self._win_rate_inline_label.setText("预估胜率  —")
            self._win_rate_inline_label.setVisible(True)

            self._apply_trade_confidence_inline(
                trade_conf, trade_conf_reasoning,
                no_order=False,
            )

        self._reasoning_edit.setPlainText(str(reasoning) if reasoning else "")
        confidence_reason = str(trade_conf_reasoning or "").strip()
        self._confidence_reasoning_edit.setPlainText(confidence_reason)
        risk = str(decision.get("risk_assessment") or "").strip()
        invalidation = str(decision.get("invalidation_condition") or "").strip()
        risk_text = risk
        if invalidation:
            risk_text = f"{risk}\n\n失效条件：{invalidation}" if risk else f"失效条件：{invalidation}"
        self._risk_reasoning_edit.setPlainText(risk_text)

        self.set_prediction(decision)

    def set_prediction(self, decision: dict) -> None:
        """Render future trend predictions in the bottom decision section."""
        self._future_trend_panel.set_prediction(decision)
        visible = (
            not self._future_trend_panel._bar_group.isHidden()
            or not self._future_trend_panel._cycle_group.isHidden()
        )
        self._future_title_label.setVisible(visible)
        self._future_trend_panel.setVisible(visible)

    def clear(self) -> None:
        self.reset_summary_metrics()
        self._trend_label.setText("趋势：—")
        self._apply_diag_chip_style(self._trend_label, color=T.FG_3)
        self._cycle_label.setText("周期：—")
        self._apply_diag_chip_style(self._cycle_label, color=T.FG_3)
        self._next_cycle_label.setText("下一周期：—")
        self._apply_diag_chip_style(self._next_cycle_label, color=T.FG_3)
        self._phase_label.setText("阶段：—")
        self._apply_diag_chip_style(self._phase_label, color=T.FG_3)
        self._phase_label.setVisible(True)
        self._support_label.setText("支撑区：—")
        self._apply_diag_chip_style(self._support_label, color=T.FG_3)
        self._resistance_label.setText("阻力区：—")
        self._apply_diag_chip_style(self._resistance_label, color=T.FG_3)

        self._diag_conf_bar.setValue(0)
        self._diag_conf_title.setVisible(False)
        self._diag_conf_bar.setVisible(False)
        self._diag_conf_label.setVisible(False)
        self._diag_reasoning_label.setVisible(False)

        self._reset_conclusion_bar_side_labels()
        self._conclusion_bar.setVisible(True)
        self._conclusion_label.setText("等待分析")
        self._conclusion_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {T.FG_3};"
        )
        self._direction_inline_label.setText("")
        self._direction_inline_label.setVisible(False)
        self._trade_prices_row.setVisible(False)
        self._trade_conf_inline_label.setVisible(False)
        self._trade_reasoning_label.setVisible(False)

        self._reasoning_edit.clear()
        self._confidence_reasoning_edit.clear()
        self._risk_reasoning_edit.clear()
        self._future_trend_panel.clear()
        self._future_title_label.setVisible(False)
        self._future_trend_panel.setVisible(False)

    def refresh_theme(self) -> None:
        """主题切换后重绘本面板：静态文字颜色跟随主题，再按缓存数据重渲。"""
        self._reasoning_edit.setStyleSheet(_reason_edit_css())
        self._diag_reasoning_label.setStyleSheet(_reason_font_css())
        self._trade_reasoning_label.setStyleSheet(_reason_font_css())
        for lbl in (self._entry_label, self._tp_label, self._tp2_label, self._sl_label):
            lbl.setStyleSheet(f"font-size: 14px; color: {T.FG};")
        self._conclusion_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {T.FG_2};"
        )
        self._direction_inline_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {T.FG_2};"
        )
        self._set_conclusion_bar_style()
        if self._last_decision is not None:
            self.set_decision(**self._last_decision)
        else:
            self.clear()

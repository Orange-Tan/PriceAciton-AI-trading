# Analysis Settings Layout v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将分析设置页按已确认原型重排，并把图表控制按钮移动到 K 线图右上角。

**Architecture:** 保留 MainWindow 现有控件与信号，仅调整 `_build_workbench` 的布局容器。分析设置继续挂载到 AISidebar；K 线图改由带工具栏的 QWidget 容器承载，工具栏复用现有按钮实例以保持行为不变。

**Tech Stack:** Python 3.11+, PyQt6, pytest。

---

### Task 1: 锁定布局契约

**Files:**
- Modify: `tests/unit/test_sidebar_layout.py`

- [ ] **Step 1: Write failing tests**

  Add tests that construct `MainWindow` and assert the visible labels are `分析品种` / `分析周期`, the three selector labels occupy separate rows, and the chart buttons are children of the chart container rather than the analysis settings content.

- [ ] **Step 2: Run focused tests**

  Run `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/unit/test_sidebar_layout.py -k analysis_settings_layout_v3` and confirm failure against the current layout.

### Task 2: Implement the minimal PyQt layout change

**Files:**
- Modify: `pa_agent/gui/main_window.py:400-640`

- [ ] **Step 1: Separate setting rows**

  Change the two label texts and place data source, symbol, and timeframe in rows 0, 1, and 2 of `ctrl_layout`; retain combo-box instances, signals, and tooltips.

- [ ] **Step 2: Move chart controls**

  Remove `_resume_chart_btn` and `_fit_chart_btn` from `ctrl_layout`; create a chart container with a top-right `QHBoxLayout`, add those same buttons there, and add the chart widget below it.

- [ ] **Step 3: Move continuous tracking above submit**

  Add `_keep_analysis_checkbox` to `ctrl_row2` before `_submit_btn`, preserving its signal and persisted-setting reset behavior.

### Task 3: Verify

**Files:**
- Test: `tests/unit/test_sidebar_layout.py`

- [ ] **Step 1: Run focused tests**

  Run `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/unit/test_sidebar_layout.py -k 'analysis_settings or workbench'`.

- [ ] **Step 2: Run related chart tests**

  Run `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/unit/test_klinechart_widget.py tests/unit/test_klinechart_overlays.py`.

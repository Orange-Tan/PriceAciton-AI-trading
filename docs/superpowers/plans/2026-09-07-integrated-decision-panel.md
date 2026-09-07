# Integrated Decision Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 将未来走势预期并入决策栏底部，并让决策页整体可垂直滚动，同时把决策标签放到实时之后、决策树之前。

**Architecture:** 复用现有 `FutureTrendPanel` 的预测渲染逻辑，将其内容挂载到 `DecisionPanel` 底部；由 `AISidebar` 用 `QScrollArea` 包裹完整决策面板。主窗口只保留一个决策面板数据入口，移除独立未来走势页的绑定。

**Tech Stack:** Python 3.11+, PyQt6, pytest, pytest-qt/offscreen GUI tests.

---

### Task 1: 先补充失败测试，锁定新布局契约

**Files:**
- Modify: `tests/unit/test_sidebar_layout.py`
- Modify: `tests/unit/test_decision_panel.py`

- [ ] **Step 1: 写测试**

  增加断言：标签顺序为“分析设置、实时、决策、决策树、决策树可视化、原始、调试”；决策页由垂直 `QScrollArea` 承载；决策面板不存在 `QToolButton` 折叠详情；未来走势区挂载在决策面板中并可通过 `set_prediction()` 显示。

- [ ] **Step 2: 运行测试确认失败**

  运行：`QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_sidebar_layout.py tests/unit/test_decision_panel.py`

  预期：新断言因现有标签顺序、独立未来走势页和折叠控件而失败。

### Task 2: 重构 DecisionPanel 为单栏内容并嵌入未来走势

**Files:**
- Modify: `pa_agent/gui/decision_panel.py`
- Modify: `pa_agent/gui/future_trend_panel.py`

- [ ] **Step 1: 取消三组可折叠详情**

  将 `QToolButton + QTextEdit` 改为普通标题 `QLabel` 加始终可见的只读 `QTextEdit`，保留原字段和更新接口。

- [ ] **Step 2: 添加底部未来走势区**

  在 `DecisionPanel` 底部创建 `FutureTrendPanel` 的内容实例，提供 `set_prediction()` 与 `clear()` 转发；隐藏嵌入实例的重复页标题/免责声明/外层分隔线，使其作为决策底部普通区块呈现。

- [ ] **Step 3: 运行面板测试**

  运行：`QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_decision_panel.py`

  预期：决策面板的新测试通过，旧的独立未来走势引用测试同步调整后通过。

### Task 3: 调整侧栏顺序并为决策页加整栏滚动

**Files:**
- Modify: `pa_agent/gui/ai_sidebar.py`
- Modify: `tests/unit/test_sidebar_layout.py`

- [ ] **Step 1: 调整标签和常量索引**

  将 `decision` 放到 `stream` 后，将 `decision_tree` 放到 `decision` 后，移除 `future_trend` 标签及其 `TAB_FUTURE_TREND` 常量；保留 `future_trend` 兼容属性仅在没有外部引用的情况下删除。

- [ ] **Step 2: 包裹决策面板**

  创建 `QScrollArea`，设置 `setWidgetResizable(True)`、垂直滚动条按需显示，将 `DecisionPanel` 作为其 widget 加入标签页。

- [ ] **Step 3: 运行侧栏测试**

  运行：`QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_sidebar_layout.py`

  预期：标签顺序、索引、滚动容器断言通过。

### Task 4: 收敛 MainWindow 数据绑定与清理路径

**Files:**
- Modify: `pa_agent/gui/main_window.py`

- [ ] **Step 1: 将预测更新统一转发给 DecisionPanel**

  在分析完成和记录回放路径中调用 `self._decision_panel.set_prediction(inner)`，删除独立 `_future_trend_panel` 更新。

- [ ] **Step 2: 清理与主题刷新统一到 DecisionPanel**

  删除单独未来走势面板的 clear/refresh 引用，避免重复状态和悬空属性。

- [ ] **Step 3: 运行完整相关测试**

  运行：`QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_sidebar_layout.py tests/unit/test_decision_panel.py tests/integration/test_next_bar_prediction.py`

  预期：全部通过；若出现与本改动无关的既有失败，记录具体测试和错误，不扩大范围。

### Task 5: GUI 构造与滚动行为验证

**Files:**
- Test: `tests/unit/test_sidebar_layout.py`

- [ ] **Step 1: 增加 offscreen 构造检查**

  构造 `AISidebar` 与 `DecisionPanel`，确认滚动区域 widget 为决策面板、预测区位于决策布局底部，调用 `clear()` 不抛异常。

- [ ] **Step 2: 运行验证**

  运行：`QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_sidebar_layout.py`

  预期：通过且无 Qt 崩溃/警告。


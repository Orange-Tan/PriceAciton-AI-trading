# Analysis Toolbar Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将分析设置迁移到参考图样式的顶部单行工具栏，直接显示数据源提供的品种字段，并让 AI 分析状态只显示在「实时」页。

**Architecture:** `MainWindow` 创建顶部横向滚动工具栏并复用现有数据源、交易所、代码、周期、获取数据、提交分析、持续跟踪控件；品种字段只从数据源元数据读取，不做本地推断。`AISidebar` 删除分析设置页，`AIStreamPanel` 成为 AI 状态唯一承载区；底部状态栏仅保留数据连接和普通操作提示。

**Tech Stack:** Python 3.11+, PyQt6, pytest, `QT_QPA_PLATFORM=offscreen`。

---

### Task 1: Move analysis controls into a single-line top toolbar

**Files:**
- Modify: `pa_agent/gui/main_window.py` in `_build_workbench` and related UI/status helpers
- Modify: `pa_agent/gui/theme/light.qss`
- Modify: `pa_agent/gui/theme/dark_gray.qss`
- Test: `tests/unit/test_sidebar_layout.py`

- [ ] **Step 1: Add failing layout assertions**

Add tests that instantiate `MainWindow` offscreen and assert: a named top toolbar exists above the workbench; its layout is horizontal; it contains the data source, exchange, auto-kind, symbol, timeframe, fetch, submit, keep-tracking, realtime indicator, and settings button in that order; the wait-close checkbox/countdown are absent; and the toolbar remains one row when the window is resized.

- [ ] **Step 2: Run the focused layout tests and verify the new assertions fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit/test_sidebar_layout.py -k "analysis_toolbar or wait_close"`

Expected: FAIL because controls are still mounted in the sidebar analysis-settings widget and no top toolbar contract exists.

- [ ] **Step 3: Implement the top toolbar with minimal structural changes**

Create a fixed-height `QScrollArea` named `analysisToolbarScroll` directly above the splitter. Put a single `QHBoxLayout` inside it with the image order. Reparent existing data source, exchange, symbol, timeframe, fetch, submit, and keep-tracking widgets into this layout. Add a read-only combo-like `QComboBox` named `instrumentKindCombo` only when the active data source exposes an explicit kind field; hide it when absent and never infer a value locally. Add a compact symbol search button that triggers the existing symbol/data alert flow. Add a realtime state label/dot and a settings `QToolButton` wired to `_open_app_settings_dialog`.

Remove the wait-close checkbox and countdown from the visible layout, and make the submit button call the immediate-submit path without consulting those widgets. Keep the existing persisted settings fields for backward-compatible config loading, but do not expose or read them from the new toolbar path. Keep chart-specific fit/resume controls in their existing chart toolbar because they are not present in the reference image.

Use object names and existing theme tokens so light and dark QSS can style the toolbar without inline color duplication. Set minimum widths only where required by the reference order; do not introduce a second responsive row.

- [ ] **Step 4: Route explicit data-source kind updates**

Read only the documented kind field from the accepted data-source frame/response after a data-source switch or `_on_refresh_frame_ready`; update `instrumentKindCombo` without emitting a user-edit signal. If the field is absent, hide the combo and its label. Never derive a kind from symbol, exchange, suffix, or regex.

- [ ] **Step 5: Run the focused layout tests and verify they pass**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit/test_sidebar_layout.py -k "analysis_toolbar or wait_close"`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the toolbar structure**

```bash
git add pa_agent/gui/main_window.py pa_agent/gui/theme/light.qss pa_agent/gui/theme/dark_gray.qss tests/unit/test_sidebar_layout.py
git commit -m "feat: move analysis controls to top toolbar"
```

### Task 2: Remove the analysis-settings tab and centralize AI status in realtime

**Files:**
- Modify: `pa_agent/gui/ai_sidebar.py`
- Modify: `pa_agent/gui/main_window.py` in `_on_status_update`, `_prepare_analysis`, `_launch_analysis_worker`, `_on_worker_done`, and status helpers
- Modify: `tests/unit/test_sidebar_layout.py`
- Test: `tests/unit/test_main_window_analysis_errors.py`

- [ ] **Step 1: Add failing status-routing tests**

Add tests that assert `AISidebar` starts with `实时` at tab index 0, has no `分析设置` tab or `set_analysis_settings_content` dependency, and that calling `_on_status_update` with preparation/analysis/completion text updates `AIStreamPanel._status_label` while leaving the top toolbar free of analysis-status labels. Add a waiting-close regression asserting no wait text/countdown widget exists.

- [ ] **Step 2: Run the focused status tests and verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit/test_sidebar_layout.py tests/unit/test_main_window_analysis_errors.py -k "realtime or analysis_status or wait_close"`

Expected: FAIL because the current sidebar still exposes `分析设置` and `_on_status_update` writes analysis messages to the bottom status bar and decision badge.

- [ ] **Step 3: Remove the sidebar analysis-settings page**

Delete the placeholder/settings widget and its tab from `AISidebar`; renumber tab constants and preserve the existing order beginning with `实时`, followed by `决策`, `决策树`, `决策树可视化`, `原始`, and `调试`. Keep `DecisionPanel` scrolling and all existing focus methods working with the new indices.

- [ ] **Step 4: Make realtime the only AI status destination**

Update `_on_status_update` and worker lifecycle methods so AI preparation, progress, retry, error, and completion messages call `AIStreamPanel.set_status`/`on_analysis_progress` only. Guard bottom `QStatusBar.showMessage` calls so they handle data-source, subscription, and ordinary chart actions but skip AI status strings. Remove decision-badge/model-label/status-strip creation and updates. Ensure the realtime indicator only reflects chart refresh pause/resume state.

- [ ] **Step 5: Run the focused status tests and verify they pass**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit/test_sidebar_layout.py tests/unit/test_main_window_analysis_errors.py -k "realtime or analysis_status or wait_close"`

Expected: all selected tests pass.

- [ ] **Step 6: Commit status routing and sidebar changes**

```bash
git add pa_agent/gui/ai_sidebar.py pa_agent/gui/main_window.py tests/unit/test_sidebar_layout.py tests/unit/test_main_window_analysis_errors.py
git commit -m "feat: centralize analysis status in realtime panel"
```

### Task 3: Full verification and UI regression review

**Files:**
- Test: `tests/unit/test_sidebar_layout.py`
- Test: `tests/unit/test_main_window_analysis_errors.py`

- [ ] **Step 1: Run all focused GUI tests**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit/test_sidebar_layout.py tests/unit/test_main_window_analysis_errors.py`

Expected: exit code 0 with no failures.

- [ ] **Step 2: Run the complete unit suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit`

Expected: exit code 0. If the repository baseline has known unit failures, compare against a pre-change run and record only failures introduced by this migration.

- [ ] **Step 3: Run formatting/lint checks on changed Python files**

Run: `.venv/bin/ruff check pa_agent/gui tests/unit && .venv/bin/black --check pa_agent/gui tests/unit`

Expected: exit code 0.

- [ ] **Step 4: Inspect the final diff and working tree**

Run: `git diff HEAD~3..HEAD --stat && git status --short --branch`

Confirm only the planned files changed, no wait/countdown UI remains, and `.superpowers/` remains untracked local metadata unless explicitly requested otherwise.

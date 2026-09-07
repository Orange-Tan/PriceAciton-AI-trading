# Silent Analysis Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分析工作线程结束后不再显示成功或错误完成类弹框/Toast，同时保留现有状态栏状态。

**Architecture:** 保持 `MainWindow._on_worker_done` 的分析收尾、按钮恢复、图表恢复和状态栏更新逻辑；在自动分析结果异常的 `_on_record_ready` / `_on_analysis_error` 路径中，保留原始页与调试信息更新，但跳过会阻塞用户的完成/错误弹框。成功结束本身只更新状态栏。不改动通用 `ToastOverlay` 或其它主动操作提示。

**Tech Stack:** Python 3.11+, PyQt6, pytest, pytest-qt（现有 GUI 测试约定）。

---

### Task 1: Add regression coverage for silent analysis completion

**Files:**
- Modify: `tests/unit/test_main_window_analysis_errors.py`
- Modify: `pa_agent/gui/main_window.py:3712-3818, 3918-3955, 4303-4338`

- [ ] **Step 1: Write the failing test**

在 `tests/unit/test_main_window_analysis_errors.py` 中为异常分析结果和未捕获分析异常各增加一个测试：用 monkeypatch 记录 `_maybe_show_truncation_help_dialog` 与 `_prompt_debug_report_for_bug_fix` 的调用，调用 `_on_record_ready` 或 `_on_analysis_error`，断言两个自动弹框入口都未被调用；同时断言错误标志和状态栏/调试记录仍被更新。另加一个成功收尾测试，调用 `_on_worker_done` 并断言状态栏仍收到“分析完成”文本且没有 Toast/弹框调用。

- [ ] **Step 2: Run test to verify it fails**

运行：

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_main_window_analysis_errors.py -k "silent or worker_done"
```

预期：测试因当前异常结果路径仍调用自动弹框入口而失败；失败应来自断言记录到调用，而不是 PyQt 初始化错误。

- [ ] **Step 3: Write minimal implementation**

在自动分析结果处理路径中移除 `_maybe_show_truncation_help_dialog` 和 `_prompt_debug_report_for_bug_fix` 的弹框调用，改为保留切换原始页、写入调试信息和状态栏错误摘要；`_on_worker_done` 继续保留 `_status_bar.showMessage(msg)` 及所有工作线程/图表收尾逻辑。不要改动其它主动操作 `QMessageBox` 调用或 `ToastOverlay` 通用实现。

- [ ] **Step 4: Run test to verify it passes**

运行：

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_main_window_analysis_errors.py -k "silent or worker_done"
```

预期：新增成功与两类异常回归测试通过。

- [ ] **Step 5: Run related GUI tests**

运行：

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/unit/test_main_window_analysis_errors.py tests/unit/test_main_window_geometry.py tests/unit/test_sidebar_layout.py
```

预期：相关测试通过。

- [ ] **Step 6: Commit implementation**

```bash
git add pa_agent/gui/main_window.py tests/unit/test_main_window_analysis_errors.py
git commit -m "fix: silence analysis completion prompts"
```

只提交本任务涉及的文件，不包含工作区中已有的其它修改。

# Workbench Sidebar Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the group selector compact and resizable, add a right-sidebar visibility control, and initialize the AI sidebar at one third of the workbench width.

**Architecture:** `WatchlistPanel` owns its inner group/stock splitter and calculates a font-metric initial group width. `MainWindow` owns the workbench splitter, a menu-bar toggle, and one-time startup pane sizing.

**Tech Stack:** Python 3.11, PyQt6, pytest.

---

### Task 1: Compact group column

**Files:**
- Modify: `pa_agent/gui/watchlist_panel.py:50-180`
- Test: `tests/unit/test_watchlist.py`

- [ ] Write the failing test.

```python
def test_group_column_width_fits_longest_group_name(qapp) -> None:
    panel = WatchlistPanel({"港股": [], "科技成长": [], "高股息红利": []})
    expected = panel._group_column_width_for(["港股", "科技成长", "高股息红利"])
    assert panel._group_splitter.sizes()[0] == expected
    assert panel._group_column.maximumWidth() > expected
```

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_watchlist.py::test_group_column_width_fits_longest_group_name` and verify it fails because the helper and splitter field do not exist.

- [ ] Add `_group_column_width_for(names)` using `fontMetrics().horizontalAdvance`, with a `56..180px` clamp and `22px` padding. Store the inner splitter in `_group_splitter`; remove the group column's fixed size policy; call `_resize_group_column()` from `set_groups()` after list population. `_resize_group_column()` must call `setSizes([group_width, remaining_width])` without changing the 1px handle.

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_watchlist.py` and commit `feat: compact watchlist group column`.

### Task 2: Approved headers and add controls

**Files:**
- Modify: `pa_agent/gui/watchlist_panel.py:50-145`
- Test: `tests/unit/test_watchlist.py`

- [ ] Write the failing test.

```python
def test_watchlist_uses_compact_group_and_stock_headers(qapp) -> None:
    panel = WatchlistPanel({"港股": []})
    assert panel._group_header.text() == "板块"
    assert panel._stock_header.text() == "自选股"
    assert panel._add_group_btn.text() == "+"
    assert panel._add_symbol_btn.text() == "+"
```

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_watchlist.py::test_watchlist_uses_compact_group_and_stock_headers` and verify it fails.

- [ ] Create column-local `_group_header` and `_stock_header` labels with muted visual style. Change both existing add actions to `+`, retain their tooltips and signals, set compact square geometry, and apply transparent icon-style hover styling.

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_watchlist.py` and commit `style: simplify watchlist headers and add controls`.

### Task 3: Right-sidebar menu toggle

**Files:**
- Modify: `pa_agent/gui/main_window.py:280-360,630-690`
- Test: `tests/unit/test_sidebar_layout.py`

- [ ] Write the failing test.

```python
def test_menu_bar_toggle_hides_and_restores_ai_sidebar() -> None:
    window = _new_window()
    window._toggle_ai_sidebar()
    assert window._ai_sidebar.isHidden()
    window._toggle_ai_sidebar()
    assert window._ai_sidebar.isVisible()
```

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_sidebar_layout.py::test_menu_bar_toggle_hides_and_restores_ai_sidebar` and verify it fails because `_toggle_ai_sidebar` does not exist.

- [ ] Store the workbench as `_workbench`. Mount a checkable `QAction` in a right-aligned `QToolButton` using `menu_bar.setCornerWidget(..., Qt.Corner.TopRightCorner)`. Use an icon glyph and alternating tooltip/accessibility text `隐藏右侧栏` / `显示右侧栏`. Capture the right pane width before hide; restore it with `QTimer.singleShot(0, ...)` after show.

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_sidebar_layout.py` and commit `feat: add AI sidebar visibility toggle`.

### Task 4: One-third startup AI sidebar

**Files:**
- Modify: `pa_agent/gui/main_window.py:630-690,4258-4272`
- Test: `tests/unit/test_sidebar_layout.py`

- [ ] Write the failing test.

```python
def test_workbench_initializes_ai_sidebar_to_one_third_width():
    window = _new_window(width=1500, height=900)
    sizes = window._workbench.sizes()
    assert abs(sizes[2] - sum(sizes) / 3) <= 2
    window.close()
```

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_sidebar_layout.py::test_workbench_initializes_ai_sidebar_to_one_third_width` and verify it fails.

- [ ] Implement `_initialize_workbench_sizes()` guarded by `_workbench_sizes_initialized`. After the first `showEvent`, schedule it with `QTimer.singleShot(0, ...)`; compute `sidebar = max(sidebar.minimumWidth(), total // 3)` and a clamped watchlist width, then set `[watchlist, chart, sidebar]`. Do not recalculate after manual drag or hide/show.

- [ ] Run `.venv-review/bin/python -m pytest -q tests/unit/test_main_window_geometry.py tests/unit/test_sidebar_layout.py tests/unit/test_watchlist.py tests/unit/test_main_window_switch.py tests/unit/test_app_settings_dialog.py` and commit `feat: size AI sidebar to one third at startup`.

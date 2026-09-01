# Adaptive Default Window Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PA Agent main window default to 90% of the primary screen's available width and height at startup.

**Architecture:** Extract the screen-size calculation into a small pure helper in `main_window.py`. `MainWindow.__init__` will pass the primary screen to that helper, preserving the existing fallback when Qt cannot provide screen information.

**Tech Stack:** Python 3.11, PyQt6, pytest.

---

### Task 1: Add coverage for adaptive sizing

**Files:**
- Create: `tests/unit/test_main_window_geometry.py`
- Modify: none in this task

- [x] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from pa_agent.gui.main_window import _default_window_size


def test_default_window_size_uses_90_percent_of_available_geometry() -> None:
    screen = SimpleNamespace(
        availableGeometry=lambda: SimpleNamespace(width=lambda: 1407, height=lambda: 923)
    )

    assert _default_window_size(screen) == (1266, 830)


def test_default_window_size_uses_fallback_without_screen() -> None:
    assert _default_window_size(None) == (1280, 820)


def test_default_window_size_uses_fallback_without_available_geometry() -> None:
    screen = SimpleNamespace(availableGeometry=lambda: None)

    assert _default_window_size(screen) == (1280, 820)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_main_window_geometry.py -q`

Expected: FAIL because `_default_window_size` does not exist yet.

### Task 2: Implement the 90% startup sizing

**Files:**
- Modify: `pa_agent/gui/main_window.py:30-45` (new helper) and `pa_agent/gui/main_window.py:222-233` (startup sizing)

- [x] **Step 1: Add the minimal helper**

```python
def _default_window_size(screen: Any | None) -> tuple[int, int]:
    """Return 90% of the primary screen's usable area, with a safe fallback."""
    available = screen.availableGeometry() if screen is not None else None
    if available is None:
        return 1280, 820
    return int(available.width() * 0.90), int(available.height() * 0.90)
```

- [x] **Step 2: Route `MainWindow` initialization through the helper**

```python
from PyQt6.QtGui import QGuiApplication

_screen = QGuiApplication.primaryScreen()
self.resize(*_default_window_size(_screen))
```

Update the nearby comment to state that the dimensions are 90% of `availableGeometry()` and therefore exclude macOS system areas.

- [x] **Step 3: Run the focused tests**

Run: `pytest tests/unit/test_main_window_geometry.py -q`

Expected: PASS (3 tests).

### Task 3: Verify the change in the existing project

**Files:**
- Test: `tests/unit/test_main_window_geometry.py`
- Test: existing unit suite and lint targets

- [x] **Step 1: Run the focused main-window tests**

Run: `pytest tests/unit/test_main_window_geometry.py tests/unit/test_main_window_switch.py -q`

Expected: PASS.

- [x] **Step 2: Run static checks for touched Python files**

Run: `ruff check pa_agent/gui/main_window.py tests/unit/test_main_window_geometry.py`

Expected: no diagnostics.

- [x] **Step 3: Run the complete unit suite**

Run: `pytest tests/unit -q`

Expected: PASS; any unrelated pre-existing failure should be reported without altering unrelated files.

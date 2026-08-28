# Watchlist Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the left watchlist into a persistent group selector plus quote/decision table, with a guarded placeholder for future group-wide AI scanning.

**Architecture:** Keep `WatchlistPanel` responsible for presentation and user signals, introduce a small settings/store adapter for group normalization and legacy migration, and let `MainWindow` provide quote/decision updates and confirmation dialogs. The existing single-symbol switch path remains intact; batch execution is explicitly out of scope and only a count/confirmation signal is exposed.

**Tech Stack:** Python 3.11, PyQt6 widgets/signals, Pydantic settings, pytest/pytest-qt.

---

## File Map

- Create: `pa_agent/gui/watchlist_store.py` — group schema, normalization, legacy `watchlist` migration, and JSON-safe serialization helpers.
- Modify: `pa_agent/config/settings.py` — add persisted `watchlist_groups` and migrate old `watchlist` values without data loss.
- Modify: `pa_agent/gui/watchlist_panel.py` — two-column group/list UI, top action buttons, quote table, decision styling, and signals.
- Modify: `pa_agent/gui/main_window.py` — pass grouped settings, update selected-group quotes from refresh frames, connect panel signals, and show scan-count confirmations.
- Create: `tests/unit/test_watchlist_store.py` — pure group-model and migration tests.
- Modify: `tests/unit/test_watchlist.py` — widget behavior, fields, styling, and scan-confirmation tests.

## Task 1: Add the Group Store and Settings Compatibility

**Files:**
- Create: `pa_agent/gui/watchlist_store.py`
- Modify: `pa_agent/config/settings.py:170-210`
- Test: `tests/unit/test_watchlist_store.py`

- [ ] **Step 1: Write failing pure-model tests**

Add tests for `normalize_watchlist_groups`, `migrate_watchlist`, and `serialize_watchlist_groups` covering: default `{"全部": []}`, deduplication, empty-name rejection, preservation of unknown symbols, and migration of `watchlist=["600519", "000001"]` into `{"全部": [...]}`.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

Run: `pytest tests/unit/test_watchlist_store.py -q`

Expected: collection succeeds and fails because `pa_agent.gui.watchlist_store` does not exist.

- [ ] **Step 3: Implement the minimal store API**

Implement:

```python
DEFAULT_GROUP = "全部"

def normalize_watchlist_groups(value: object) -> dict[str, list[str]]: ...
def migrate_watchlist(groups: object, legacy_symbols: object) -> dict[str, list[str]]: ...
def serialize_watchlist_groups(groups: dict[str, list[str]]) -> dict[str, list[str]]: ...
```

Normalize names with stripped text, keep `全部` first, deduplicate symbols within each group, and return a fresh dict. `migrate_watchlist` must use explicit groups when valid and otherwise copy the legacy list into `全部`.

- [ ] **Step 4: Extend `GeneralSettings`**

Add `watchlist_groups: dict[str, list[str]] = Field(default_factory=lambda: {"全部": []})`. In a `model_validator(mode="before")`, call `migrate_watchlist(data.get("watchlist_groups"), data.get("watchlist"))`, then leave the existing `watchlist` field readable for backward compatibility. Do not remove or rewrite the old field until the new structure has been serialized.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/unit/test_watchlist_store.py tests/unit/test_settings_round_trip.py -q`

Expected: PASS. Commit with `git add pa_agent/gui/watchlist_store.py pa_agent/config/settings.py tests/unit/test_watchlist_store.py && git commit -m "feat: add persistent watchlist groups"`.

## Task 2: Replace the Single List UI with Groups and Quote Rows

**Files:**
- Modify: `pa_agent/gui/watchlist_panel.py`
- Test: `tests/unit/test_watchlist.py`

- [ ] **Step 1: Write failing widget tests**

Add pytest-qt tests that instantiate `WatchlistPanel({"全部": ["600519"]})` and assert:

```python
assert panel.groups() == {"全部": ["600519"]}
assert panel.current_group() == "全部"
panel.add_group("核心持仓")
panel.add_symbol("600519", group="核心持仓") is True
panel.add_symbol("600519", group="核心持仓") is False  # duplicate in group
panel.update_quote("600519", name="贵州茅台", price="1488", change="+1.25%")
assert [panel._table.item(0, c).text() for c in range(4)] == ["600519", "贵州茅台", "1488", "+1.25%"]
```

Also assert `update_decision("600519", "买入", date=today)` uses red text, `update_decision(..., "卖出", date=today)` uses green text, and an older date uses the dark-gray role/color.

- [ ] **Step 2: Run tests and verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/unit/test_watchlist.py -q`

Expected: FAIL because the current panel has no group API or table.

- [ ] **Step 3: Implement group column and top action row**

Use a horizontal splitter/layout inside `WatchlistPanel`: a narrow `QListWidget` for groups on the left and a `QTableWidget` on the right. Put `＋ 新增板块`, `＋ 添加自选股`, and `分析当前板块` above the table. Keep delete actions in a compact context/button row. Add signals:

```python
groups_changed = pyqtSignal()
group_selected = pyqtSignal(str)
symbol_selected = pyqtSignal(str)
scan_requested = pyqtSignal(str, int)
```

Preserve the existing `list_changed` signal as a compatibility alias emitted with group changes.

- [ ] **Step 4: Implement group and row APIs**

Implement `groups`, `set_groups`, `current_group`, `add_group`, `rename_group(old_name, new_name)`, `remove_current_group`, `add_symbol(symbol, group=None)`, `remove_selected`, `update_quote`, `update_decision`, and `symbols(group=None)`. The `全部` group is always present and cannot be deleted or renamed. A symbol is unique per group. Use `QTableWidget` columns `代码`, `名称`, `现价`, `今日涨幅`, `今日决策`; empty values are empty strings, not placeholders.

- [ ] **Step 5: Implement decision-date styling and scan confirmation signal**

Store row metadata with `Qt.ItemDataRole.UserRole`. Style only same-day `买入` red and same-day `卖出` green; all other decisions use `T.FG_2`. On scan button click emit `scan_requested(current_group, count)` after showing the count. For count `> 5`, show a `QMessageBox.question` warning containing “将消耗较多 token”; emit only on confirmation. For count `0`, show an information dialog and emit nothing.

- [ ] **Step 6: Run widget tests and commit**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/unit/test_watchlist.py -q`

Expected: PASS. Commit with `git add pa_agent/gui/watchlist_panel.py tests/unit/test_watchlist.py && git commit -m "feat: add grouped watchlist table"`.

## Task 3: Wire Groups, Quotes, and Legacy Persistence in MainWindow

**Files:**
- Modify: `pa_agent/gui/main_window.py:625-650,1440-1460,1810-1900`
- Modify: `pa_agent/config/settings.py` if serialization adjustments are required
- Test: `tests/unit/test_watchlist.py`

- [ ] **Step 1: Add failing wiring tests**

Test that `_build_workbench` passes `settings.general.watchlist_groups` to `WatchlistPanel`, `_persist_watchlist` writes both `watchlist_groups` and a flattened compatibility `watchlist`, and `_on_watchlist_group_selected` keeps the current symbol switch untouched. Add a quote update test using a fake quote mapping shaped as `{"600519": {"name": "贵州茅台", "price": 1488.0, "change_pct": 1.25}}`; the helper must format it as `1488` and `+1.25%`.

- [ ] **Step 2: Run tests and verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/unit/test_watchlist.py -q`

Expected: FAIL because the main window still reads only `general.watchlist` and has no group-selection wiring.

- [ ] **Step 3: Pass grouped data and connect signals**

Initialize the panel from `settings.general.watchlist_groups`; connect `group_selected` to a slot that refreshes visible rows, `groups_changed`/`list_changed` to persistence, `symbol_selected` to the existing switch method, and `scan_requested` to a placeholder handler that reports “批量分析功能即将支持” without launching workers.

- [ ] **Step 4: Persist grouped and flattened forms**

Update `_persist_watchlist` to assign a normalized group dict to `settings.general.watchlist_groups` and a flattened, deduplicated list to `settings.general.watchlist`, then call the existing `save_settings`. Preserve unrelated settings.

- [ ] **Step 5: Update quote cells from refresh data**

Add `_watchlist_quote_snapshot()` returning `dict[str, dict[str, object]]` with keys `name`, `price`, and `change_pct`. In `_on_refresh_frame_ready`, after the existing chart update path, call it and pass each result to `watchlist_panel.update_quote(symbol, name=..., price=..., change=...)`. Update only rows in the active group; on missing values pass empty strings. Wrap extraction and formatting in `try/except` so a bad or unavailable quote never blocks the refresh loop.

- [ ] **Step 6: Run tests and commit**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/unit/test_watchlist.py tests/unit/test_main_window_switch.py -q`

Expected: PASS. Commit with `git add pa_agent/gui/main_window.py pa_agent/config/settings.py tests/unit/test_watchlist.py && git commit -m "feat: wire grouped watchlist into main window"`.

## Task 4: Add Decision Data Adapter and Final Verification

**Files:**
- Create: `pa_agent/gui/watchlist_decisions.py`
- Modify: `pa_agent/gui/main_window.py:3380-3480`
- Test: `tests/unit/test_watchlist.py`

- [ ] **Step 1: Write failing decision-adapter tests**

Test `decision_for_record(record, today)` returns `(text, date)` for `买入`/`卖出`, returns empty text for missing or malformed records, and preserves the record date for styling. Add a same-day boundary test using the local midnight date rather than a rolling 24-hour window.

- [ ] **Step 2: Implement the adapter**

Read only completed Stage-2 decision data already available in the analysis record. Return empty text when no decision exists. Keep the adapter pure and tolerant of missing keys.

- [ ] **Step 3: Push decisions into the visible table**

After a successful analysis result, call `watchlist_panel.update_decision(symbol, text, date)` for the analyzed symbol. The table must not show historical decisions as current-color signals.

- [ ] **Step 4: Run focused and broad checks**

Run:

```bash
QT_QPA_PLATFORM=offscreen pytest tests/unit/test_watchlist.py tests/unit/test_watchlist_store.py tests/unit/test_main_window_switch.py -q
python3 -m compileall -q pa_agent/gui pa_agent/config tests/unit/test_watchlist.py tests/unit/test_watchlist_store.py
git diff --check
```

Expected: all available tests pass; if PyQt6/pytest is unavailable, report that limitation and retain the compile check result.

- [ ] **Step 5: Commit final adapter and tests**

Run: `git add pa_agent/gui/watchlist_decisions.py pa_agent/gui/main_window.py tests/unit/test_watchlist.py && git commit -m "feat: show watchlist decision summaries"`.

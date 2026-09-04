# KLineChart 图表替换实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用本地 KLineChart Canvas 页面替换主图 TradingView 页面，并保留 Python 图表接口、程序 overlay 和用户交互画线。

**Architecture:** `TradingViewChartWidget` 继续作为兼容容器，但内部加载本地 KLineChart 页面。Python 通过 JSON 编码的 JavaScript bridge 推送全量/增量 K 线和程序 overlay；页面内部用 KLineChart 管理 Canvas、价格线、标记和用户 overlay。无 WebEngine 时继续使用 PyQtGraph fallback。

**Tech Stack:** PyQt6 QWebEngineView, KLineChart 10.x, HTML5 Canvas, JavaScript bridge, pytest, compileall。

---

### Task 1: 准备 KLineChart 本地静态资源和页面

**Files:**
- Create: `tradingview/klinechart/klinecharts.min.js`
- Modify: `tradingview/pa_agent_chart.html`
- Test: `tests/unit/test_klinechart_page.py`

- [ ] **Step 1: 写页面契约测试**

测试页面必须引用本地 KLineChart 资源，并声明 `PAChart.setData`、`updateData`、`setProgramOverlays`、`clearProgramOverlays`、`setInteractionMode` 方法；禁止继续引用 TradingView Charting Library 和 UDF bundle。

- [ ] **Step 2: 运行测试确认失败**

运行：`./.venv/bin/python -m pytest -q tests/unit/test_klinechart_page.py --tb=short`

预期：失败，因为当前页面仍引用 `charting_library-master`，且缺少 KLineChart bridge 方法。

- [ ] **Step 3: 获取并固定本地 KLineChart 构建产物**

使用 npm 安装固定版本并生成浏览器可加载的 UMD/standalone 文件，将产物放入 `tradingview/klinechart/`。运行时不依赖 Node/npm。

- [ ] **Step 4: 重写 HTML 图表页面**

页面使用 `klinecharts.min.js` 初始化 Canvas 图表，定义：

```javascript
window.PAChart = {
  setData: function (bars) {},
  updateData: function (bar) {},
  setProgramOverlays: function (items) {},
  clearProgramOverlays: function () {},
  setInteractionMode: function (mode) {}
};
```

实现 K 线全量加载、最新 bar 增量更新、程序 overlay 分组清理和水平线/买卖点映射。

- [ ] **Step 5: 运行页面契约测试确认通过**

运行：`./.venv/bin/python -m pytest -q tests/unit/test_klinechart_page.py --tb=short`

预期：PASS。

- [ ] **Step 6: 提交页面资源变更**

```bash
git add tradingview/klinechart tradingview/pa_agent_chart.html tests/unit/test_klinechart_page.py
git commit -m "feat: add local klinechart page"
```

### Task 2: 改造 Python WebEngine bridge 和数据同步

**Files:**
- Modify: `pa_agent/gui/tradingview_chart_widget.py`
- Modify: `pa_agent/data/base.py`（仅在需要时复用已有 bar 字段，不新增模型字段）
- Test: `tests/unit/test_tradingview_chart_widget.py`

- [ ] **Step 1: 写 bridge payload 测试**

覆盖空帧、时间升序、重复时间戳去重、首次全量同步、相同 symbol/timeframe 不重复初始化、页面未 ready 时缓存状态。

- [ ] **Step 2: 运行测试确认失败**

运行：`QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q tests/unit/test_tradingview_chart_widget.py --tb=short`

预期：失败，因为当前 widget 只发送 `setFrame`，且未实现 bar payload 和 pending bridge 状态。

- [ ] **Step 3: 实现 Python payload 和 ready 队列**

在 `TradingViewChartWidget` 中增加：

```python
_pending_payload: dict[str, Any] = {}
_last_bar_signature: tuple[Any, ...] | None = None
```

新增私有方法 `_frame_payload(frame)`、`_sync_pending()`；`set_frame` 在页面未 ready 时缓存最新 frame，ready 后发送 `setData`，后续只发送 `updateData`。所有 JavaScript 参数通过 `json.dumps` 编码。

- [ ] **Step 4: 保留兼容方法并连接 overlay API**

`set_decision`、`clear_decision_overlay`、`set_support_resistance`、`clear_support_resistance` 改为调用 `setProgramOverlays`/`clearProgramOverlays`，不改变调用方签名。

- [ ] **Step 5: 运行 bridge 测试确认通过**

运行：`QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q tests/unit/test_tradingview_chart_widget.py --tb=short`

预期：PASS。

- [ ] **Step 6: 提交 bridge 变更**

```bash
git add pa_agent/gui/tradingview_chart_widget.py tests/unit/test_tradingview_chart_widget.py
git commit -m "feat: bridge klinechart data and overlays"
```

### Task 3: 完善程序标记和用户交互画线

**Files:**
- Modify: `tradingview/pa_agent_chart.html`
- Modify: `pa_agent/gui/main_window.py`（仅在已有图表设置入口接入交互模式）
- Test: `tests/unit/test_klinechart_overlays.py`

- [ ] **Step 1: 写 overlay 行为测试**

覆盖支撑、阻力、Entry、TP1、TP2、SL 的颜色和标签；买入/卖出标记的方向；清理程序 overlay 不影响用户 overlay。

- [ ] **Step 2: 运行测试确认失败**

运行：`./.venv/bin/python -m pytest -q tests/unit/test_klinechart_overlays.py --tb=short`

预期：失败，因为当前页面的 overlay 方法为空或仅保存变量。

- [ ] **Step 3: 实现 overlay 分组和交互模式**

程序 overlay 使用固定 `groupId = "program"`，用户 overlay 使用 `groupId = "user"`；程序 overlay 默认锁定，用户 overlay 默认可编辑。实现水平线、趋势线和矩形入口，并监听 overlay 完成/移动/删除事件。

- [ ] **Step 4: 运行 overlay 测试确认通过**

运行：`./.venv/bin/python -m pytest -q tests/unit/test_klinechart_overlays.py --tb=short`

预期：PASS。

- [ ] **Step 5: 提交 overlay 变更**

```bash
git add tradingview/pa_agent_chart.html pa_agent/gui/main_window.py tests/unit/test_klinechart_overlays.py
git commit -m "feat: support klinechart program and user overlays"
```

### Task 4: 集成验证和回退路径检查

**Files:**
- Modify: `tradingview/README.md`
- Test: `tests/unit/test_chart_backend_selection.py`

- [ ] **Step 1: 写后端选择和资源检查测试**

验证 WebEngine 可用时加载 KLineChart widget；WebEngine 不可用时仍使用 PyQtGraph；本地资源存在且页面不依赖远程脚本。

- [ ] **Step 2: 运行测试确认失败**

运行：`QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q tests/unit/test_chart_backend_selection.py --tb=short`

预期：至少资源引用检查失败，直到 README 和页面路径完成更新。

- [ ] **Step 3: 更新资源说明并修复集成问题**

文档说明 KLineChart 资源、Apache 2.0 NOTICE、构建方式和运行时不需要 Node/npm；确保页面通过 `QUrl.fromLocalFile` 加载本地脚本。

- [ ] **Step 4: 运行最终验证**

```bash
QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q \
  tests/unit/test_klinechart_page.py \
  tests/unit/test_tradingview_chart_widget.py \
  tests/unit/test_klinechart_overlays.py \
  tests/unit/test_chart_backend_selection.py \
  tests/unit/test_chart_widget_no_lines_when_not_trading.py
./.venv/bin/python -m compileall -q pa_agent tests
git diff --check
```

预期：新增/相关测试全部通过，编译和差异检查退出码为 0；若完整测试存在既有失败，单独记录失败文件和原因，不掩盖结果。

- [ ] **Step 5: 提交集成变更**

```bash
git add tradingview/README.md tests/unit/test_chart_backend_selection.py
git commit -m "test: verify klinechart chart backend"
```

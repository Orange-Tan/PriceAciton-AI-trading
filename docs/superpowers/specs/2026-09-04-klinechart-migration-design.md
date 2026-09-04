# KLineChart 图表替换设计

## 目标

将项目的主 K 线图从当前 TradingView Charting Library 替换为本地 KLineChart Canvas 页面，同时保留现有 Python 图表接口，并支持程序标记和用户交互画线。

## 范围

- 保留 `ChartWidget` 对外使用的 `set_frame`、`set_frame_now`、`fit_view`、`set_decision`、`set_support_resistance` 等接口。
- 使用 PyQt6 `QWebEngineView` 加载本地 KLineChart 页面。
- 首次加载通过 JSON 全量设置 OHLCV，后续只更新最后一根或追加的新 K 线。
- 程序绘制支撑、阻力、Entry、TP1、TP2、SL 水平线和买卖点标记。
- 支持用户创建、移动、删除水平线和趋势线等 overlay。
- 用户绘制结果通过 JS bridge 回传 Python，仅保留运行时内存状态。
- 没有 Qt WebEngine 时继续使用现有 PyQtGraph 回退。
- 保留现有 TradingView 资源，不做删除性清理。

## 架构与数据流

```text
KlineFrame
  -> TradingViewChartWidget.set_frame
  -> QWebEngine JavaScript bridge
  -> KLineChart applyNewData / updateData
  -> Canvas 绘制
```

图表页面提供一个稳定的 `PAChart` API：

- `setData(bars)`：替换完整 K 线数据。
- `updateData(bar)`：更新当前最后一根或追加一根 K 线。
- `setProgramOverlays(items)`：替换程序生成的线和标记。
- `clearProgramOverlays()`：清理程序生成的线和标记。
- `setInteractionMode(mode)`：切换用户水平线、趋势线等绘制工具。

程序 overlay 与用户 overlay 使用不同的 `groupId`，清理程序标记时不能影响用户绘图。

## 数据约束

- K 线按时间升序发送给前端。
- 时间戳统一使用毫秒，并在 Python 侧去重。
- 空帧传递空数组，不触发 JavaScript 异常。
- 增量更新只发送发生变化的最新 bar，避免每秒重建全量数据。
- JS bridge 不拼接未经 JSON 编码的字符串，所有 payload 使用 `json.dumps`。

## 图形映射

- 支撑/阻力/Entry/TP/SL：KLineChart 水平线 overlay。
- 买入：绿色向上箭头或标签，绑定到指定 bar 时间和价格。
- 卖出：红色向下箭头或标签，绑定到指定 bar 时间和价格。
- 用户趋势线：两点 overlay，允许拖动。
- 程序生成的 overlay：默认锁定，用户 overlay：默认可编辑。

## 错误处理与兼容

- WebEngine 不可用时沿用 PyQtGraph fallback。
- 页面尚未 ready 时缓存最新 frame 和 overlay 状态，ready 后一次性同步。
- JavaScript 调用失败不应阻塞 Python 数据线程；记录日志并保留 Python 状态。
- 页面关闭时释放 WebEngine 页面和前端状态，不启动新的后台数据服务。

## 测试策略

- 单测 KlineFrame 到前端 bar payload 的排序、去重、空帧和增量逻辑。
- 单测 overlay payload 的价格、方向、标签、锁定状态和清理分组。
- 单测 WebEngine 不可用时的 fallback 选择。
- 使用静态检查确认 HTML 中所有 bridge 方法存在且 JSON 参数经过编码。
- 运行相关 pytest、`compileall` 和 `git diff --check`。

## 非目标

- 本次不实现用户绘图的磁盘持久化或跨会话恢复。
- 本次不删除旧 TradingView 资源。
- 本次不重构数据源和 AI 决策逻辑。

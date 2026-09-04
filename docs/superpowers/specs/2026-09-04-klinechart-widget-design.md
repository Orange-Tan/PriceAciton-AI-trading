# KLineChart Widget Migration Design

## Goal

将现有图表后端正式命名并收敛为 `KLineChartWidget`，移除 `TradingViewChartWidget` 方案及旧 TradingView Charting Library/UDF 运行时依赖，同时保留 PyQtGraph 作为无 WebEngine 时的回退。

## Architecture

`KLineChartWidget` 继续继承 `QWebEngineView`，加载 `tradingview/pa_agent_chart.html` 和本地 `klinechart/klinecharts.min.js`。Python 侧通过 JSON JavaScript bridge 推送 `KlineFrame` 的升序 OHLCV 数据，并调用 `setData`、`updateData`、`setProgramOverlays` 与 `fit`。程序标记按 `program` 分组且锁定，用户画线按 `user` 分组并保持可编辑。

主窗口只依赖统一的图表接口，不再导入或引用 `TradingViewChartWidget`、UDF 服务或 TradingView 专用命名。WebEngine 不可用时继续构造现有 `ChartWidget`（PyQtGraph）。旧静态 Charting Library 资源从运行路径和发布说明中移除；保留 KLineChart 及其依赖的许可证和 NOTICE 文件。

## Data and Compatibility

保留 `set_frame`、`set_frame_now`、`reset`、`fit_view`、`set_decision`、`set_support_resistance` 等调用方接口。首帧或品种/周期变化发送全量数据；仅最新 bar 变化时发送增量更新。所有时间戳去重并按升序传输，空帧发送空数据。决策和支撑阻力转换为图表无关的 overlay payload。

## Verification

新增/更新测试覆盖类名和导入路径、页面本地资源、bridge payload、首帧与增量同步、overlay 分组、WebEngine 回退和旧 TradingView/UDF 引用清理。最终运行相关 pytest、`compileall`、Ruff/Black 检查，并用 `git diff --check` 验证差异。

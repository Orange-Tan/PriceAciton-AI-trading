# TradingView 图表资源

本目录包含 PA Agent 嵌入式图表所需的本地资源：

- `pa_agent_chart.html`：Qt WebEngine 加载的 KLineChart 页面。
- `klinechart/klinecharts.min.js`：KLineChart 10.0.3 本地 UMD 构建产物。
- `charting_library-master/`：旧版 TradingView 资源，暂保留用于兼容和回滚。

运行时，`pa_agent/gui/tradingview_chart_widget.py` 通过 Qt WebEngine 将 `KlineFrame` 转为 JSON 推送给 KLineChart。首次更新使用全量数据，后续更新只发送最后一根 K 线；目录缺失时将回退到 pyqtgraph 图表。

KLineChart 资源由 npm 包构建得到，开发环境需要 Node.js/npm，用户运行时不需要 Node.js。重新构建时固定使用 `klinecharts@10.0.3`，并同步保留本目录的 `LICENSE`、`NOTICE` 和 `LICENSE-lightweight-charts`。

## 许可证

这些资源来自 TradingView Charting Library 分发包。上传、分发、修改和部署前必须遵守 TradingView 的使用条款以及本目录和上游分发包中随附的许可证文件。不要将访问令牌、账户信息或私有市场数据写入本目录。

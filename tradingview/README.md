# TradingView 图表资源

本目录包含 PA Agent 嵌入式图表所需的本地资源：

- `pa_agent_chart.html`：Qt WebEngine 加载的图表页面。
- `charting_library-master/charting_library/`：TradingView Charting Library 静态文件。
- `charting_library-master/datafeeds/udf/dist/`：UDF 数据源适配器构建产物。

运行时，`pa_agent/gui/tradingview_chart_widget.py` 会启动本地 UDF 服务，将 PA Agent 的 `KlineFrame` 提供给图表页面。目录缺失时，嵌入式 TradingView 图表无法加载。

## 许可证

这些资源来自 TradingView Charting Library 分发包。上传、分发、修改和部署前必须遵守 TradingView 的使用条款以及本目录和上游分发包中随附的许可证文件。不要将访问令牌、账户信息或私有市场数据写入本目录。

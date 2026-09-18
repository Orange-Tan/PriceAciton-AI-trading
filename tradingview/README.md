# KLineChart 图表资源

本目录包含 PA Agent 嵌入式图表所需的本地资源：

- `pa_agent_chart.html`：Qt WebEngine 加载的 KLineChart 页面。
- `klinechart/klinecharts.min.js`：KLineChart 10.0.3 本地 UMD 构建产物。

运行时，`pa_agent/gui/klinechart_widget.py` 通过 Qt WebEngine 将 `KlineFrame` 转为 JSON 推送给 KLineChart。首次更新使用全量数据，后续更新只发送最后一根 K 线；Qt WebEngine 不可用时将回退到 PyQtGraph 图表。

KLineChart 资源由 npm 包构建得到，开发环境需要 Node.js/npm，用户运行时不需要 Node.js。重新构建时固定使用 `klinecharts@10.0.3`，并同步保留本目录的 `LICENSE`、`NOTICE` 和 `LICENSE-lightweight-charts`。

## 许可证

KLineChart 及其依赖的许可证和 NOTICE 文件随资源一同保留。不要将访问令牌、账户信息或私有市场数据写入本目录。

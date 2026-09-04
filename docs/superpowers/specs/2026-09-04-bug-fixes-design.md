# PA Agent Bug Fixes Design

## Scope

修复四项已确认的运行问题：

1. 阶段二“不下单”结果携带价格字段时必须被校验拒绝，而不是静默清空后保存。
2. 下一根 K 线预测的概率并列时采用稳定、可重复的方向选择规则。
3. 嵌入式 TradingView 图表必须实际绘制/清除交易决策线和支撑阻力线。
4. 嵌入式 TradingView 图表必须跟随应用主题切换。

不在本轮调整历史测试契约、联网测试策略或已存在的工作区删除操作。

## Design

### Stage 2 validation

在归一化阶段保留模型原始字段用于 schema/语义检查；仅对已确认合法的不下单结果应用默认值。带有任意非空价格、方向或入场依据字段的不下单结果返回 category-c，编排器走现有 Stage2Failed 和 partial-save 路径。

### Prediction tie handling

归一化后按固定顺序 `bullish -> bearish -> neutral` 选择最大概率方向。并列时不保留模型任意选择，保证相同输入产生相同输出；不可预测分支仍保持 direction/probabilities 为 null。

### TradingView overlays

扩展网页桥接 API：使用 Lightweight Chart/TradingView 原生图形 API 创建和清理水平线及价格标签。Python 端继续发送 JSON，不改变 ChartWidget 的兼容接口；无效或不完整价格数据只清理对应覆盖层，不影响 K 线显示。

### Theme synchronization

Python 端向网页桥接发送主题 token（背景、网格、文字、涨跌颜色），网页端更新图表 overrides。主题切换失败时保留当前图表和数据，不抛出 UI 线程异常。

## Testing

- 为不下单字段不变量增加最小 validator/orchestrator 回归测试，并验证合法不下单仍通过。
- 为预测并列概率增加确定性测试，覆盖全零和普通并列。
- 为 TradingView 桥接增加 JavaScript 可调用 API 的单元级契约测试，验证 set/clear 行为和主题参数传递。
- 运行相关测试、`compileall`，并记录未纳入本轮的历史测试契约失败。

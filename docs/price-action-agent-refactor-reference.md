# 价格行为投资智能体重构参考

## 目标

将 PA Agent 从“桌面程序直接拼提示词并调用单一模型 API”演进为可扩展的投资分析应用：外壳管理数据、图表和配置；分析引擎调度多 Agent；技术流派以可版本化 Skill/能力包接入。系统仅输出研究结论，不连接券商或自动下单。

配套可迁移 Skill 位于
[`reference/price-action-investment-analysis`](../reference/price-action-investment-analysis)。它抽取了现有项目的关键不变量：已收盘 K 线快照、两阶段分析、策略路由、结构化输出和保守的无交易路径。

## 推荐架构

```text
投资应用外壳
  ├─ 自选、数据源配置、K 线和结果可视化
  ├─ 冻结快照与技术特征计算
  └─ 记录、回放、告警和用户权限
          ↓
分析引擎（厂商无关）
  ├─ 任务编排、取消、超时和事件流
  ├─ 输入/输出 schema 校验和审计
  ├─ 技能/能力选择与多 Agent 汇总
  └─ Agent CLI Adapter
          ↓
Codex CLI / Claude Code / 其他兼容 Agent
  ├─ price-action-investment-analysis Skill
  └─ 技术分析能力插件或 MCP 工具
```

不要让 GUI 直接拼 Agent CLI 命令，也不要让任一 Agent 直接操作行情账户。`AnalysisEngine` 是稳定边界：它把应用数据转换为统一任务协议，并把厂商原始事件转换为统一的 `reasoning`、`content`、`tool`、`error` 和 `completed` 事件。

## 外壳与工具协议

外壳提供事实；Agent 负责解释。每项事实都需带来源、计算参数和 K 线范围，避免模型从图像或过时数据猜测。

| 工具/功能 | 责任 | Agent 可见输出 |
| --- | --- | --- |
| `market_snapshot` | 获取、清洗和冻结已收盘 K 线 | 可审计 OHLCV JSON，K1 为最新已收盘棒 |
| `indicator_features` | EMA/ATR、几何、重叠、波段等确定性计算 | 对齐每根 K 线的数值与特征 |
| `level_detector` | 支撑阻力、趋势线、前高低、测量目标 | 带 `source`、`bar_range` 的候选水平 |
| `setup_detector` | 标记候选形态，不作最终交易决定 | 候选 setup、置信度和证据 |
| `analysis_history` | 保存快照、结论和后续结果 | 只读相似案例与增量分析上下文 |
| `chart_renderer` | 绘制事实、候选和最终决策标记 | 不开放给 Agent 写任意图形 |

三类图表标记必须分开：程序确定的 `fact_markers`、程序检测的
`candidate_setups`、经过分析引擎校验后才绘制的 `decision_markers`。

## Skill 与能力包

价格行为 Skill 负责 Al Brooks 风格的市场结构、逐棒解释、通道/区间/突破/反转和两阶段决策方法。它不取行情、不发订单、不保存用户数据。

其他技术流派作为独立能力包按需加载，例如：波浪理论、量价、均线系统、缠论、形态统计或基本面事件。每个能力包应声明：输入 schema、输出 schema、可用市场、所需时间框架、可提供的证据以及不适用条件。协调 Agent 不应把不同流派的结论简单投票平均，而应保留分歧和证据来源。

## 分析流程

1. 外壳获取数据，排除未收盘 K 线，计算指标并冻结快照。
2. 引擎执行输入校验；数据不足或异常时直接返回，不启动 Agent。
3. Agent 使用核心价格行为 Skill 输出 Stage 1 市场诊断。
4. 引擎校验 Stage 1；`wait` 直接结束，`proceed` 则由路由器选择策略包。
5. Agent 使用 Stage 1、同一快照和策略包输出 Stage 2 决策评估。
6. 引擎校验三价、方向和终态一致性，保存完整审计记录。
7. 外壳绘制结果。只有显式授权的独立模块才能把结果发送到外部系统；默认没有交易执行能力。

## 多 Agent 模式

建议首版采用“协调者 + 可选专家”的模式：

- 协调者：唯一拥有 Stage 1/Stage 2 最终 JSON 输出权。
- 价格行为专家：运行核心 Skill，解释市场结构。
- 技术流派专家：只产出标准化证据报告，不直接给交易指令。
- 审计/反方专家：只检查矛盾、数据时效、风险和无交易理由。

所有专家看到同一快照版本。协调者必须引用采纳或拒绝的关键证据；发生冲突且无法消解时，默认 `wait`。

## Agent CLI Adapter

为 Codex CLI 和 Claude Code 分别实现 Adapter，但对上层暴露同一个接口：

```text
run(task, skill_paths, allowed_tools, timeout, cancel_token) -> event stream
```

Adapter 负责认证检查、临时工作目录、stdin/文件输入、流式输出解析、进程取消、超时、原始日志脱敏和退出码映射。Skill 和策略包通过只读工作目录提供；默认不给 Agent 网络、shell 写权限或未声明的工具。若某厂商 CLI 无法稳定返回结构化输出，保留其原始响应并由引擎判为不可用，而不是猜测修复。

## 验收与演进

首个重构版本应验证：同一冻结快照在不同 CLI 中能产生可解析的两阶段结果；Stage 1 的 `wait` 不调用 Stage 2；`wait/reject` 不出现价格标记；程序事实与最终图表标记可追溯；取消、超时、格式错误均不会污染历史记录。

先迁移价格行为 Skill 与三个配套脚本，再实现一个 Codex CLI Adapter；随后再接入 Claude Code 和一个只读技术流派专家。不要在第一版同时引入自动交易、多数据源重写、回测平台和全部流派。

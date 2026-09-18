# PA Agent

PA Agent 是一个桌面端价格行为（Price Action）分析工具：从行情数据源读取 K 线，经过两阶段 AI 流程（市场诊断 → 交易决策）生成结构化分析结果。它不连接券商、不执行下单，所有结果仅供研究参考。

## 功能

- TradingView、AkShare、东方财富、Tushare、通达信、腾讯财经多数据源
- 本地 KLineChart 图表与 PyQtGraph 后备图表
- 两阶段分析、增量分析、持续跟踪和下一根 K 线预期
- 决策树可视化、分析原始响应、Token 用量和完整记录落盘
- 分析后自由追问与历史经验库
- JSON 校验、语义检查、截断修复和失败重试
- API Key 与第三方凭据使用系统凭据库，不写入配置文件

## 环境要求

- macOS 12+ 或 Windows 10/11
- Python 3.11+
- 可访问所选 AI API 的网络
- 至少一个可用行情数据源

## 安装与启动

```bash
git clone https://github.com/rosemarycox5334-debug/PA_Agent.git
cd PA_Agent
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pa_agent.main
```

开发依赖：

```bash
python -m pip install -e ".[dev]"
```

首次启动后打开“设置 → 模型 API”，填写 Base URL、模型名和 API Key。不要把 API Key 直接写入 `config/settings.json`。

## 凭据隔离

不同客户端的凭据使用独立的系统凭据槽位，避免切换客户端时相互覆盖：

| 路由 | 模型别名 | 凭据来源 |
| --- | --- | --- |
| QClaw | `openclaw` / `openclaw/*` | QClaw 本地 Gateway 配置，写入 `provider_api_key:qclaw` |
| WorkBuddy | `openclaw_wb` / `openclaw_wb/*` | WorkBuddy 会话或环境变量，写入 `provider_api_key:workbuddy` |
| Cursor | `openclaw_cs` / `openclaw_cs/*` | Cursor SDK 登录凭据，写入 `provider_api_key:cursor` |

API Key、Feishu `app_secret`/`secret`、Tushare Token 等敏感值只在运行时使用。配置文件和 GitHub 示例必须保持为空值；如果密钥曾经提交过，请立即作废并轮换。

## 配置文件

```bash
cp config/settings.example.json config/settings.json
```

运行时配置、分析记录、日志和个人经验库默认被 `.gitignore` 忽略。字段说明见 [`config/README.md`](config/README.md)。

## 数据源说明

- TradingView：全球外汇、贵金属、股票、指数、期货和加密货币；依赖 `tvDatafeed`。
- AkShare / 东方财富 / Tushare / 通达信 / 腾讯财经：主要用于 A 股和指数；部分来源需要 Token 或本地网络条件。
- 可在“设置 → 数据源”中逐个检测连通性。

KLineChart 嵌入图表资源位于 `tradingview/`，源码运行时必须保留该目录。

## 测试与检查

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/unit
python -m compileall -q pa_agent tests
python -m ruff check pa_agent --select F,E9
```

部分旧测试仍依赖历史 UI/API 契约；看到失败时请先确认测试是否对应当前产品设计。

## 文档

- [完整使用文档](PA_Agent使用文档.md)
- [macOS 部署](MAC版本智能体部署方法.txt)
- [Windows 部署](windows智能体部署方法--喂给智能体帮你安装.txt)
- [配置与凭据说明](config/README.md)
- [安全策略](SECURITY.md)

## 免责声明与许可证

本工具仅供学习和研究，不构成投资建议。交易有风险，使用者自行承担决策后果。

项目代码采用 [AGPL-3.0](LICENSE) 发布；`tradingview/` 下的第三方资源请同时遵守其附带许可证和 NOTICE。

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

PA Agent 是一个 PyQt6 桌面应用，读取 K 线数据并将预计算特征送入大语言模型做**两阶段价格行为（Price Action）分析**（市场诊断 → 交易决策）。它只做分析，**不**连接券商、**不**执行下单。界面与大量策略提示词均为中文。

## 常用命令

安装（`dev` 附加依赖会拉取 pytest、pytest-qt、hypothesis、ruff、black）：

```bash
pip install -e ".[dev]"
```

启动 GUI：

```bash
python -m pa_agent.main      # 或：python run.py
```

- macOS 下系统自带的 `/usr/bin/python3` 没有 PyQt6，请使用附带的启动脚本 `运行智能体.command`：它会自动探测装了 PyQt6 的解释器（`~/.workbuddy/.../bin/python3`、homebrew 等），并自动探测本地代理给 TradingView 用。

运行测试：

```bash
pytest -q                                       # 全部用例
pytest tests/unit/test_data_source_factory.py   # 单个文件
pytest tests/unit/test_data_source_factory.py::test_create_data_source_returns_expected_types   # 单个用例
pytest -m "not e2e"                             # 跳过端到端
```

- 标记（markers）：`unit`、`property`（hypothesis）、`integration`、`e2e`、`live`（通过环境变量提供真实 API Key，绝不读取 `config/settings.json`）。
- 多数用例是纯 Python（不依赖 Qt）；涉及 GUI 的用例用 `pytest-qt`，可加 `QT_QPA_PLATFORM=offscreen` 无头运行。

代码检查 / 格式化（行长 100，目标 py3.11）：

```bash
ruff check pa_agent tests
black --check .
make lint    # ruff check . && black --check .
```

安装用于拦截密钥/配置/日志误提交的 pre-commit 钩子（Windows/PowerShell）：

```powershell
make setup-secrets
```

## 架构

整个应用通过一个依赖容器串联，不使用全局单例：

- [`pa_agent/main.py`](pa_agent/main.py) → `AppContext.bootstrap()` → `MainWindow`。
- [`pa_agent/app_context.py`](pa_agent/app_context.py) —— `AppContext`（`@dataclass(slots=True)`）持有 `settings`、`event_bus`、`data_source`、`client`、`assembler`、`router`、`validator`、`pending_writer`、`exp_reader`、`ledger`，并分发给 GUI 组件与编排器。新增共享资源时在这里接线。

### 配置层（`pa_agent/config/`）

- `settings.py` —— Pydantic v2 的 `Settings`，包含子模型：`provider`（model/base_url/api_key/thinking/reasoning_effort）、`general`、`prompt`、`validation`、`feishu`、`pushplus`、`tushare`。`load_settings`/`save_settings` 读写 `config/settings.json`，加载时做旧字段迁移。
- `paths.py` —— 所有运行时路径都以 `PROJECT_ROOT` 为根定义成常量。请 import 使用，不要硬编码路径。
- `model_providers.py` —— 模型厂商预设目录（DeepSeek、OpenAI 及国内厂商），含 `base_url` + 型号列表，以及 `guess_provider`/`find_provider`。

### 数据层（`pa_agent/data/`）

- `base.py` 定义核心类型：`KlineBar`、`KlineFrame`（不可变，`bars[0]` 为最新/形成中的 K 线）、`IndicatorBundle`，以及 `DataSource` 抽象基类（`connect/subscribe/latest_snapshot`）。
- `factory.py` —— `create_data_source(kind)` 与 `normalize_data_source_kind()`；`DataSourceKind` 是 `settings.py` 里的 `Literal`。实现：`tradingview.py`（tvDatafeed）、`akshare_source.py`、`eastmoney_source.py`（含 `eastmoney_baostock.py` 兜底）、`tushare_source.py`、`tdx_source.py`（通达信，pytdx）、`tencent_source.py`（腾讯财经，curl_cffi）。
- `snapshot.py` / `refresh_loop.py` —— 轮询刷新；`bar_close_wait.py` —— 等待 K 线收盘。

### AI 与编排层

- `ai/deepseek_client.py` —— OpenAI 兼容客户端（`base_url` + `model` + `api_key`），按厂商处理 thinking/reasoning 参数。`ai/cursor_sdk_client.py` 处理特殊的 `is_openclaw_cs_model` 场景；`cursor_connector.py`、`qclaw_connector.py`、`workbuddy_connector.py` 在启动时从外部 IDE/智能体同步 provider 配置。
- `ai/prompt_assembler.py` 基于 `prompt_engineering/*.txt` 策略文件（只读）与经验库拼装提示词；`ai/router.py`（`route_strategy_files`）为给定的市场诊断挑选策略文件。
- `orchestrator/two_stage.py` 是核心流水线：阶段一诊断 → 校验 → 路由策略 → 载入经验 → 阶段二决策 → 校验 → 落盘。`orchestrator/free_chat.py` 是分析后追问；`orchestrator/validation_retry.py` 封装校验重试。
- 校验与归一化：`ai/json_validator.py`（schema）、`ai/stage1_normalizer.py` / `ai/stage2_normalizer.py`（归一化 LLM JSON）、`ai/coherence_checks.py`、`ai/trace_semantic_checks.py`、`ai/retry_policy.py`。
- `ai/decision_tree.py` + `ai/decision_nodes.py` 生成决策树可视化数据。

### 记录 / 通知 / GUI

- `records/` —— `pending_writer.py`（落盘分析记录，写入前会脱敏 API Key）、`schema.py`（`AnalysisRecord`）、`analysis_history.py`、`experience_reader.py`、`trade_logger.py`。
- `notify/` —— `feishu_notifier.py`（webhook + HMAC 签名，及扫码绑定单聊的 `im/v1/messages` 推送）、`feishu_scan.py`（扫码一键创建机器人并绑定：飞书 Device Authorization Grant 协议，成功后返回 app_id/app_secret/用户 open_id）、`pushplus_notifier.py`。扫码界面在 `gui/feishu_scan_dialog.py`（二维码渲染依赖可选包 `segno`，未装时降级为链接+浏览器打开）。
- `gui/` —— `main_window.py` 是大型主窗口（4000+ 行）。统一设置对话框是 `app_settings_dialog.py`（菜单栏「设置」，左侧模块栏：数据源 / 模型 API / 飞书通知 + 通用设置四组）；`feishu_settings_dialog.py` 与 `general_settings_dialog.py` 暴露可复用的 `*Panel(QWidget)` 类。`chart_widget.py` / `widgets/` 负责 pyqtgraph 绘图。`gui/theme/` 是应用主题：三套 `*.qss`（深灰 `dark_gray` / 深蓝 `dark_blue` / 浅色 `light`）+ `tokens.py`（主题调色板，`T.*` 在运行期解析为当前主题值，需用 `T.*` 而非硬编码颜色）+ `apply.py`（`apply_theme(app, kind)` 全局应用）。主题由「设置 → 图表与界面 → 界面风格」切换并持久化到 `settings.general.theme`；涉及硬编码颜色的组件需提供 `refresh_theme()` 并在 `MainWindow._refresh_theme_ui` 中调用。

## 约定与注意点

- **绝不提交运行时/密钥文件。** `config/settings.json`（存有真实 API Key）、`config/exception_state.json`、`config/tv_symbol_aliases.json`、`logs/`、`records/pending/`、`experience/`、`trade_records/` 均被 `.gitignore` 忽略。pre-commit 钩子还会扫描暂存 diff 中的 `sk-…` / `api_key` 内容。
- API Key 在日志/界面中通过 `util/mask_secret.py` 与 `util/logging.py`（`configure_logging`、`update_api_key`）脱敏。不要明文打印或记录 Key。
- 数据源种类是 `pa_agent/config/settings.py` 中的封闭 `Literal`——新增数据源时，需同步修改该 `Literal`、`data/factory.py`（`DATA_SOURCE_CHOICES` / `_DEFAULT_SYMBOLS`）以及 `gui/app_settings_dialog.py` 里的 `DATA_SOURCE_INFO` 三处。
- 数据源在 `create_data_source` 内部惰性 import；缺少某个可选依赖（例如 macOS 下的 `MetaTrader5`）不应导致整个包 import 失败。
- `prompt_engineering/*.txt` 是运行时策略输入而非文档——修改它们会改变分析行为，可能需要同步更新 `tests/unit/test_prompt_txt_files.py`。

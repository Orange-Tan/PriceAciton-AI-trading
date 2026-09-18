# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目规则

使用中文编写文档和推理回复。

## 项目简介

PA Agent 是一个 PyQt6 桌面应用，读取 K 线数据并将预计算特征送入大语言模型做**两阶段价格行为（Price Action）分析**（市场诊断 → 交易决策）。它只做分析，**不**连接券商、**不**执行下单。界面与大量策略提示词均为中文。

核心不变量（改代码前先确认没有破坏它）：**送进模型的分析快照只包含已收盘 K 线，`K1` = 最新一根已收盘 K 线**。图表在实时模式下最右侧多画一根空心「未收盘棒」，点击「提交分析」后图表冻结、该棒消失，从而保证图上 `#1` 与 JSON 里的 `K1` 是同一根。详见 [`docs/图表K线与分析快照说明.md`](docs/图表K线与分析快照说明.md)。

## 常用命令

安装（`dev` 附加依赖会拉取 pytest、pytest-qt、hypothesis、ruff、black）：

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

启动 GUI：

```bash
python -m pa_agent.main      # 或：python run.py
```

- macOS 下系统自带的 `/usr/bin/python3` 没有 PyQt6，请使用附带的启动脚本 `运行智能体.command`：它会按顺序探测装有 PyQt6 的解释器（`./.venv`、`~/.workbuddy/binaries/python/versions/*`、homebrew、`python3`），并探测本地代理端口（7890/7897/1087/8118/10809）后导出 `PA_TV_PROXY` 供 TradingView 数据源使用。

运行测试：

```bash
pytest -q                                       # 全部用例
pytest tests/unit/test_data_source_factory.py   # 单个文件
pytest tests/unit/test_data_source_factory.py::test_create_data_source_returns_expected_types   # 单个用例
pytest -m "not e2e"                             # 跳过端到端
QT_QPA_PLATFORM=offscreen pytest -q tests/unit  # 无头跑涉及 GUI 的用例
```

- 标记（markers，定义在 `pyproject.toml`）：`unit`、`property`（hypothesis）、`integration`、`e2e`、`live`（通过环境变量提供真实 API Key，绝不读取 `config/settings.json`）。
- `tests/integration/conftest.py` 提供两阶段流水线的样板数据与 fixture：`VALID_STAGE1` / `VALID_STAGE2`（结构完整的阶段一/二 JSON）、`make_reply()`、`make_frame()`（20 根多头 K 线，可通过 preflight 闸门）、`frame` / `pending_writer` / `assembler` / `exp_reader` fixture。写新的编排层用例优先复用它们。

代码检查 / 格式化（行长 100，目标 py3.11）：

```bash
ruff check pa_agent tests
black --check .
make lint    # ruff check . && black --check .
```

- CI（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）跑在 `windows-latest`，**只做安装 + `import pa_agent` 冒烟**，不跑测试；本地跑测试是唯一保障。

安装用于拦截密钥/配置/日志误提交的 pre-commit 钩子：

```powershell
make setup-secrets   # → tools/setup_git_secrets.ps1，Windows 专用
```

- 该脚本是 PowerShell，macOS/Linux 上直接跑会失败；手动等价操作是 `git config core.hooksPath .githooks` 加 `git update-index --chmod=+x .githooks/pre-commit`。

## 架构

整个应用通过一个依赖容器串联，不使用全局单例：

- [`pa_agent/main.py`](pa_agent/main.py) → 崩溃诊断 + 日志 → `QApplication` → `apply_theme` → `AppContext.bootstrap()` → `MainWindow`。
- [`pa_agent/app_context.py`](pa_agent/app_context.py) —— `AppContext`（`@dataclass(slots=True)`）持有 `settings`、`event_bus`、`data_source`、`client`、`assembler`、`router`、`validator`、`pending_writer`、`exp_reader`、`ledger`，并分发给 GUI 组件与编排器。新增共享资源时在这里接线。
- `MainWindow` 通过 `_build_orchestrator()`（`gui/main_window.py:4776`）用 ctx 里的组件构造 `TwoStageOrchestrator`，**任何组件缺失就返回 `None`**（分析入口随之禁用）——新增必需依赖时注意这个全或无判断。
- **`EventBus` 不是主链路**：它只有 `data_frame` / `status` / `exception` / `token_update` 四个信号，而 `MainWindow._connect_event_bus`（`main_window.py:854`）实际只订阅 `status`；真正的数据流是各 worker 的 `pyqtSignal` 直连。不要以为它是应用骨架。

### 配置层（`pa_agent/config/`）

- `settings.py` —— Pydantic v2 的 `Settings`，包含子模型：`provider`（model/base_url/api_key/thinking/reasoning_effort/context_window）、`general`、`prompt`、`validation`、`feishu`、`pushplus`、`tushare`。`load_settings`/`save_settings` 读写 `config/settings.json`，加载时做旧字段迁移（`dark_blue` 主题、`cost_warning_threshold_pct`、`default_bar_count`、旧数据源名 `adata`/`a_share`/`mt5`/`yfinance` 等）。
- **API Key 不进配置文件**：`load_settings` 从系统凭据库读取（`keyring`，service `pa-agent`），`save_settings` 写回时把 `provider.api_key`、`feishu.app_secret`、`feishu.secret` 强制置空。三个外部客户端路由使用**独立凭据槽位**（`_keyring_username_for_provider`，`settings.py:15`）：`openclaw*` → `provider_api_key:qclaw`、`openclaw_wb*` → `provider_api_key:workbuddy`、`openclaw_cs*` → `provider_api_key:cursor`，避免切换路由时互相覆盖。字段含义详见 [`config/README.md`](config/README.md)。
- `paths.py` —— 所有运行时路径都以 `PROJECT_ROOT` 为根定义成常量。请 import 使用，不要硬编码路径。
- `model_providers.py` —— 模型厂商预设目录（DeepSeek、OpenAI 及国内厂商），含 `base_url` + 型号列表，以及 `guess_provider`/`find_provider`。
- `watchlist_store.py` —— 自选股分组数据的迁移/规范化（与 `gui/watchlist_store.py` 不是同一个模块）。

### 数据层（`pa_agent/data/`）

- `base.py` 定义核心类型：`KlineBar`、`KlineFrame`（不可变，**`bars[0]` 为最新**，实时模式下即形成中的 K 线）、`IndicatorBundle`，以及 `DataSource` 抽象基类（`connect/subscribe/latest_snapshot`）。
- `factory.py` —— `create_data_source(kind)`、`normalize_data_source_kind()`、`probe_data_source()`（带超时/并发信号量的连通性探测）与国内来源探测缓存。实现：`tradingview.py`（tvDatafeed，需网络代理）、`akshare_source.py`、`eastmoney_source.py`（含 `eastmoney_baostock.py` 兜底）、`tushare_source.py`（需 Token）、`tdx_source.py`（通达信，pytdx）、`tencent_source.py`（腾讯财经，curl_cffi）。
- `snapshot.py` / `refresh_loop.py` / `refresh_policy.py` —— 轮询刷新与快照组装。**`build_analysis_frame`（送模型的路径）会丢掉 `bars[0]` 的形成中棒，并多取 `INDICATOR_WARMUP_BARS = 50` 根更老的棒算 EMA20/ATR14 后再切片**（保证最前面几根指标不是 `nan`）；`build_live_frame` 只给 UI 用、保留形成中棒。`bar_close_wait.py` —— 等待 K 线收盘（用 `elapsed % duration` 而非 `ts_open + duration`，以容忍数据源时区偏移）；`kline_adjust.py` —— 前复权/后复权（注意是**进程级可变状态**，不是按数据源隔离的）。
- 数据源在 `create_data_source` 内部惰性 import；缺少某个可选依赖（例如 macOS 下不可用的 Windows-only 依赖）不应导致整个包 import 失败。

### AI 与编排层

- `orchestrator/two_stage.py` 是核心流水线：预检闸门 → 阶段一诊断 → 校验（可重试）→ `route_strategy_files` 路由策略 → 载入经验 → **`gate_result` 短路**（`wait`/`unknown` 时不调用模型，直接用 `build_stage2_gate_wait_response` 造阶段二结果）→ 阶段二决策 → 校验（可重试）→ 落盘。每个阶段前后都检查 `CancelToken`；网络/鉴权错误会被捕获并记进部分记录，而不是抛出。`submit()` 的返回记录**总是完整填充到中断点**（成功/校验失败/取消/网络错误都一样）。
- `orchestrator/free_chat.py` 是分析后追问：`FreeChatSession` 的 `_build_prefix` 只在会话开始时构建一次并逐轮复用（保前缀缓存）；其中「上一轮 assistant」消息是**从校验过的 `stage2_decision` + 原始 `kline_data` 合成**的，**绝不回放 `stage2_response.content`**——把模型自己的散文当事实喂回去会固化幻觉（错误棒型、虚构影线）。`orchestrator/validation_retry.py` 封装校验重试（`validate_with_retry`，可回注反馈轮次后重调 API）。
- `ai/prompt_assembler.py` 基于 `prompt_engineering/*.txt` 策略文件（只读）与经验库拼装提示词：`build_stage1` / `build_incremental_stage1`（增量分析，带上一轮诊断）/ `build_stage2_continuation`。`ai/router.py`（`route_strategy_files`）按阶段一的 `cycle_position`/`direction`/`detected_patterns` 挑选策略文件，是**纯函数**。
- **系统提示词必须逐字节稳定**：阶段一与阶段二的 system prompt 是同一个 `_build_shared_system_prompt_inner()` 产物（`prompt_assembler.py:939`，经进程级 `_SYSTEM_PROMPT_CACHE` 缓存），阶段二的 KV 前缀缓存、增量分析的四消息链（system / 上一轮 user / 上一轮 assistant / 增量续问）全都依赖这一点。改它等于让所有缓存失效。
- `ai/router.py` 的 `_ALL_VALID_FILES`（`router.py:54`）是**封闭集合**——策略文件名来自阶段一输出并按此校验；新增/改名 `prompt_engineering/*.txt` 必须同步它。
- `ai/deepseek_client.py` —— OpenAI 兼容客户端（`base_url` + `model` + `api_key`），按厂商处理 thinking/reasoning 参数并流式回调 reasoning/content。`ai/cursor_sdk_client.py` 处理 `is_openclaw_cs_model` 场景；`cursor_connector.py`、`qclaw_connector.py`、`workbuddy_connector.py` 在启动时从外部 IDE/智能体同步 provider 配置，并在网络错误时提供自动回退（`two_stage.py` 的 `_stream_chat_resilient`）。
- 校验与归一化：`ai/json_validator.py`（schema + 错误分类 a–e）、`ai/stage1_normalizer.py` / `ai/stage2_normalizer.py`（归一化 LLM JSON）、`ai/coherence_checks.py`、`ai/trace_semantic_checks.py`、`ai/retry_policy.py`。`validation` 设置决定 lenient/strict、是否开各类语义检查、重试次数上限。
- **重试策略的硬约束**（`ai/retry_policy.py`）：分类 `e`（额度耗尽）**从不重试**；`metrics:` / `trace:§14` / `s2:order_direction` 视为实质错误不重试；重试时不允许模型偷改诊断——`IMMUTABLE_FIELDS`（阶段一 `direction`/`cycle_position`/`gate_result`）在反馈未点名的情况下被改动，整次尝试按分类 `c` 失败并标记 `cheat_detected`（`detect_cheat`）。
- 决策相关：`ai/decision_tree.py` + `ai/decision_nodes.py`（决策树与节点判定、preflight 数据闸门）、`decision_continuity.py`、`decision_stance.py`（保守/均衡/激进/极激进）、`structure_levels.py`、`trend_context.py`、`pattern_routing.py`、`cycle_enums.py`。
- `ai/session_ledger.py` 累计 token 用量与上下文占用（`AIUsage` 汇入 `total_input`/`total_cached_input`/`total_output`，`ledger.add()` 后发 `updated`）。**已知不一致**：`general.context_warning_threshold_pct` 只喂给 ledger 的 `threshold_crossed` 信号，而该信号全仓库无人订阅；真正弹的「上下文用量警告」是 `gui/ai_stream_window.py` 与 `gui/conversation_widget.py` 里硬编码的 80%/95%，所以这个设置项目前不影响弹窗。`ai/token_counter.py` 没有调用方。

### 记录 / 通知 / GUI

- `records/` —— `pending_writer.py`（落盘分析记录，分 `save_full` / `save_partial`，写入前脱敏 API Key）、`schema.py`（`AnalysisRecord` / `RecordMeta`）、`analysis_history.py`、`experience_reader.py`、`trade_logger.py`。
- 记录可能**天生不完整**：`save_partial` 会在序列化字典里塞一个不属于模型的 `_partial_reason` 键（`user_cancelled` / `insufficient_data` / `auth_error` / `network_error` / `user_switched` / `stage1_*` / `stage2_*`），`demo/record_loader.py` 读取时会剥掉它。落盘失败只记日志和 `disk_error` 事件，**从不抛出**——持久化不能拖垮一次分析。
- `records/analysis_history.py` 名字有误导性：它与经验库/历史浏览无关，只服务于**增量分析**（找上一条成功记录、算新增已收盘 K 线数）。
- `records/experience_reader.py` 是**只读**的，代码库里没有任何地方写 `success_cases/` / `failure_cases/`（经验库靠外部脚本或手工维护）。且 `prompt.experience_max_entries` 默认为 `0`，即默认不注入经验。
- `notify/` —— `feishu_notifier.py`（webhook + HMAC 签名，及扫码绑定单聊的 `im/v1/messages` 推送）、`feishu_scan.py`（扫码一键创建机器人并绑定：飞书 Device Authorization Grant 协议，成功后返回 app_id/app_secret/用户 open_id）、`pushplus_notifier.py`。扫码界面在 `gui/feishu_scan_dialog.py`（二维码渲染依赖可选包 `segno`，未装时降级为链接+浏览器打开）。
- **通知不是事件驱动的**：只有阶段二真的给出下单方案、且 `general.alert_on_order_opportunity` 打开时，`MainWindow._maybe_alert_order_opportunity`（`main_window.py:4361`）才会返回真，进而 `_spawn_post_order_followup`（`main_window.py:4280`）在守护线程里存交易 CSV/图、并推送飞书（PushPlus 仅在配置了 token 时）。推送失败只记日志，绝不影响主流程。
- `demo/` —— 离线演示/回放：`record_loader.py` 从 `records/pending/` 读取历史 `AnalysisRecord`，`replayer.py`（`DemoReplayer`）用 QTimer 重放成与实时分析**相同的信号序列**。它是 GUI 功能（工具栏演示按钮 → `_on_demo_mode_button`，`main_window.py:2584`），不是 CLI。
- `gui/` —— `main_window.py` 是大型主窗口（4800+ 行）。统一设置对话框是 `app_settings_dialog.py`（菜单栏「设置」，左侧模块栏：数据源 / 模型 API / 飞书通知 + `GeneralSettingsPanel.SECTION_TITLES` 的交易决策 / 分析行为 / 图表与界面 / 决策树可视化）；`feishu_settings_dialog.py`、`general_settings_dialog.py` 暴露可复用的 `*Panel(QWidget)` 类（负责控件与 `load_values`/`apply_values`，**不含导航**），宿主对话框负责排版与切换。`chart_widget.py` / `widgets/` 负责 pyqtgraph 绘图。
- 设置对话框**只写配置**：数据源切换发生在 `exec()` 返回之后由 `MainWindow` 读取 `dlg.selected_data_source_kind` 再调 `_select_data_source_kind(...)`（`main_window.py:4560` 附近），同一段还负责同步 client provider、调试面板 API Key、`update_api_key()`、图表显示设置与 `_refresh_theme_ui()`。
- **图表后端按依赖自动二选一、无开关**：`klinechart_available()`（`gui/klinechart_widget.py:22`）能 import `PyQt6.QtWebEngineWidgets` 就用 `KLineChartWidget`（WebEngine 载入仓库根 `tradingview/pa_agent_chart.html`），否则退回 `ChartWidget`（pyqtgraph）；选择在 `main_window.py:745` 构造时一次性决定，不持久化。`pyproject.toml` 只依赖 `PyQt6`，**没列 WebEngine**，所以默认安装走的是 pyqtgraph 后备路径。两个后端实现同一套鸭子类型接口（`set_frame` / `set_decision` / `set_support_resistance` / `refresh_theme` 等），没有 ABC。
- `gui/theme/` 是应用主题：**两套** `*.qss`（深灰 `dark_gray` / 浅色 `light`）+ `tokens.py`（主题调色板，`T.*` 在运行期解析为当前主题值，**必须用 `T.*` 而非硬编码颜色**）+ `apply.py`（`apply_theme(app, kind)` / `apply_theme_from_settings` 全局应用）。主题由「设置 → 图表与界面 → 界面风格」切换并持久化到 `settings.general.theme`（`ThemeKind`，`settings.py:87`）；涉及硬编码颜色的组件需提供 `refresh_theme()` 并在 `MainWindow._refresh_theme_ui`（`main_window.py:4503`）中调用。旧配置里的 `dark_blue` 会在加载时回退为 `light`。
- `gui/stage2_payload.py` 的 `prepare_stage2_for_ui()` 是**面板看到阶段二结果前的必经归一化**（补 next_bar/next_cycle 预测、展平内层 `decision`）；把原始阶段二 JSON 直接喂给面板会出错。
- **线程约定**：worker 一律 `QThread` + `pyqtSignal`，从不碰控件；UI 槽先判存活（`_ui_is_alive()` / `_qobject_alive()`），过期结果靠 `_analysis_worker_id` 丢弃，`_disconnect_analysis_worker` 在拆解前断开全部信号。停止刷新循环时会强制关掉 TradingView websocket 并 join，超时未退出的线程作为 zombie 寄存、之后由 `_reap_zombie_workers` 回收。**UI 线程上不做任何网络 I/O。**
- `gui/main_window.py` 里对 `pa_agent.gui.*` 的 import 大多是**函数内局部 import**，用来打断循环依赖并加快启动——不要提到模块顶层。
- 自选股的真实实现在 `config/watchlist_store.py`（Qt 无关），`gui/watchlist_store.py` 只是兼容再导出；自选股批量扫描（`scan_requested`）目前是未实现的桩。

## 约定与注意点

- **绝不提交运行时/密钥文件。** `config/settings.json`、`config/exception_state.json`、`config/tv_symbol_aliases.json`、`logs/`、`records/`、`experience/`、`trade_records/` 均被 `.gitignore` 忽略。pre-commit 钩子（`.githooks/pre-commit`）还会扫描暂存 diff 中的 `sk-…` / `api_key` 内容。
- API Key 在日志/界面中通过 `util/mask_secret.py` 与 `util/logging.py`（`configure_logging`、`update_api_key`）脱敏。不要明文打印或记录 Key，也不要在 shell 里把它 echo 出来。
- 数据源种类是 `pa_agent/config/settings.py` 中的封闭 `Literal`（`DataSourceKind`）——新增数据源时，需同步修改该 `Literal`、`data/factory.py`（`DataSourceKind` / `DATA_SOURCE_CHOICES` / `_DEFAULT_SYMBOLS`）、`data/market_defaults.py` 以及 `gui/app_settings_dialog.py` 里的 `DATA_SOURCE_INFO` 四处。
- `prompt_engineering/*.txt` 是运行时策略输入而非文档——修改它们会改变分析行为，可能需要同步更新 `tests/unit/test_prompt_txt_files.py` 与 `ai/router.py` 的文件名常量表。
- `tradingview/` 是 KLineChart 嵌入图表的运行时资源，源码运行时必须保留该目录（第三方资源，另有其许可证与 NOTICE）。注意仓库根的 `klinechart/` 只剩 `__pycache__`，是废弃目录，不是资源位置。
- 几处**容易误判的“有但没用”**：`pa_agent/security/` 只有一个 docstring，真正的密钥处理在 `config/settings.py`（keyring）+ `util/mask_secret.py`；`ai/token_counter.py` 全仓库无调用方；`general.analysis_mode`（`gui/analysis_modes.py`）目前是预留接缝、无行为差异；`gui/widgets/chart_panel.py` 与 `SettingsDialog` 等旧对话框已不被 `MainWindow` 使用。
- [`reference/price-action-investment-analysis/`](reference/price-action-investment-analysis) 是抽取出来对外发布的 Skill 与契约文档（`references/analysis-contract.md` 同样以 `K1` = 最新已收盘棒为准）；[`docs/price-action-agent-refactor-reference.md`](docs/price-action-agent-refactor-reference.md) 描述了向多 Agent / Agent CLI Adapter 演进的推荐架构——属于方向性文档，不是当前实现。

# PA Agent Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按风险顺序修复 PA Agent 中已确认的启动、分析错误处理、API 错误分类、数据源探测、关闭阻塞、凭据泄露和配置持久化问题，并同步测试契约。

**Architecture:** 保持现有 Qt、Pydantic 和数据源抽象不变，在边界层增加防御式错误处理和可控生命周期。配置加载采用“校验失败即隔离并回退”的策略，网络探测采用请求级超时优先、线程池兜底，所有用户可见错误保留原始错误上下文。

**Tech Stack:** Python 3、PySide/Qt、Pydantic、pytest、httpx/OpenAI SDK、tvDatafeed。

---

## 当前执行状态

- [x] Task 1：分析异常展示防二次崩溃（提交 `6e64ad2`，2 个回归测试通过）
- [x] Task 2：配置校验失败隔离并回退（已完成本地回归验证）
- [x] Task 3：API 错误分类修正（已完成本地回归验证）
- [ ] Task 4：数据源探测请求级 timeout 与资源回收（当前仅保留线程池兜底，底层 tvDatafeed 仍需请求级取消）
- [x] Task 5：窗口关闭非阻塞清理（已完成编译、lint 和 Qt 回归测试）
- [x] Task 6：清理明文 Feishu 凭据（配置文件及污染样例已清空）
- [x] Task 7：配置原子保存（已完成本地回归验证）
- [ ] Task 8：同步旧测试契约并恢复完整测试门禁（当前仍有 24 个旧契约失败）

### Task 1: 防止分析异常展示二次崩溃

**Files:**
- Modify: `pa_agent/gui/main_window.py:3743-3810`
- Test: `tests/unit/test_main_window_analysis_errors.py`

- [ ] **Step 1: 写失败测试，覆盖调试面板不存在和控件已销毁两种情况**

```python
def test_analysis_error_is_reported_without_debug_widget(qtbot, main_window, record):
    main_window._debug_widget = None
    record.exception = {"type": "provider_error", "message": "boom"}
    main_window._on_record_ready_impl(record)
    assert main_window._last_analysis_had_error is True


def test_analysis_error_survives_debug_widget_runtime_error(qtbot, main_window, record, monkeypatch):
    record.exception = {"type": "provider_error", "message": "boom"}
    monkeypatch.setattr(main_window._debug_widget, "add_turn", lambda _: (_ for _ in ()).throw(RuntimeError("deleted")))
    main_window._on_record_ready_impl(record)
    assert main_window._last_analysis_had_error is True
```

- [ ] **Step 2: 运行测试确认当前实现失败**

Run: `QT_QPA_PLATFORM=offscreen .venv-review/bin/python -m pytest -q tests/unit/test_main_window_analysis_errors.py -q`

Expected: 至少一个用例因 `debug.add_turn` 的 `AttributeError` 或 `RuntimeError` 失败。

- [ ] **Step 3: 实现最小修复**

将异常 turn 写入封装为局部安全函数，仅在 `debug is not None` 时调用，并捕获 `AttributeError`、`RuntimeError`；无调试面板时继续执行状态栏和错误对话框逻辑，不吞掉日志中的原始异常。

- [ ] **Step 4: 运行测试确认通过**

Run: `QT_QPA_PLATFORM=offscreen .venv-review/bin/python -m pytest -q tests/unit/test_main_window_analysis_errors.py`

Expected: 所有用例 PASS。

- [ ] **Step 5: 提交该独立修复**

```bash
git add pa_agent/gui/main_window.py tests/unit/test_main_window_analysis_errors.py
git commit -m "fix: guard analysis error debug reporting"
```

### Task 2: 配置校验失败时隔离坏配置并回退

**Files:**
- Modify: `pa_agent/config/settings.py:360-430`
- Test: `tests/unit/test_settings_recovery.py`

- [ ] **Step 1: 写失败测试，覆盖类型、范围和嵌套字段错误**

```python
@pytest.mark.parametrize("payload", [
    {"general": {"analysis_bar_count": "abc"}},
    {"provider": {"thinking": "not-bool"}},
    {"validation": {"retry_max": -1}},
    {"feishu": {"enabled": "maybe"}},
])
def test_load_settings_recovers_from_validation_error(tmp_path, payload):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    settings = load_settings(path)
    assert isinstance(settings, Settings)
    assert path.with_suffix(".json.invalid").exists()
```

- [ ] **Step 2: 运行测试确认当前实现抛出 ValidationError**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_settings_recovery.py -q`

Expected: 当前实现直接抛 `pydantic.ValidationError`。

- [ ] **Step 3: 捕获并恢复配置**

在 `Settings.model_validate(raw)` 外捕获 `ValidationError`：先将原文件原样复制为 `settings.json.invalid`（已存在时追加时间戳），记录字段错误摘要，再以 `Settings()` 默认值继续；不要把异常中的 API key 或 secret 写入日志。

- [ ] **Step 4: 运行恢复测试及现有设置测试**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_settings_recovery.py tests/unit/test_settings*.py`

Expected: 新增用例及既有设置用例全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add pa_agent/config/settings.py tests/unit/test_settings_recovery.py
git commit -m "fix: recover from invalid settings values"
```

### Task 3: 修正 API 错误分类和重试策略

**Files:**
- Modify: `pa_agent/orchestrator/two_stage.py:1195-1260`
- Test: `tests/unit/test_api_error_classification.py`

- [ ] **Step 1: 写失败测试**

```python
def test_invalid_request_is_not_auth_error():
    exc = RuntimeError('{"type":"invalid_request_error","message":"bad parameter"}')
    assert TwoStageOrchestrator._is_auth_error(exc) is False


@pytest.mark.parametrize("status", [400, 404, 422])
def test_client_status_is_not_network_error(status, openai_status_error):
    assert TwoStageOrchestrator._is_network_error(openai_status_error(status)) is False


def test_rate_limit_is_classified_separately(openai_status_error):
    assert TwoStageOrchestrator._classify_api_error(openai_status_error(429)) == "rate_limit"
```

- [ ] **Step 2: 运行测试确认误判**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_api_error_classification.py -q`

Expected: 当前 `invalid_request_error` 被判为鉴权，400/404/422 被判为网络错误。

- [ ] **Step 3: 实现明确分类**

仅保留 401/403 和明确 credential 标记为 `auth_error`；将 429 归为 `rate_limit`；400/404/422 归为 `request_error`；仅 `APITimeoutError`、`APIConnectionError` 及 httpx 连接/读取超时归为 `network_error`。让 fallback/retry 分支只消费对应类别。

- [ ] **Step 4: 运行相关 orchestrator 测试**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_api_error_classification.py tests/unit/test_provider_override_by_model.py tests/unit/test_deepseek_client.py`

Expected: 新分类用例通过；如旧测试仍断言旧契约，更新断言以匹配当前 provider 路由设计。

- [ ] **Step 5: 提交**

```bash
git add pa_agent/orchestrator/two_stage.py tests/unit/test_api_error_classification.py
git commit -m "fix: classify provider errors accurately"
```

### Task 4: 让数据源探测真正可取消并限制资源残留

**Files:**
- Modify: `pa_agent/data/tradingview_connectivity.py:20-65`
- Modify: `pa_agent/data/factory.py:120-155`
- Test: `tests/unit/test_data_source_probe_timeout.py`

- [ ] **Step 1: 写超时和取消测试**

```python
def test_tradingview_probe_uses_request_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr("tvDatafeed.TvDatafeed.get_hist", lambda *a, **kw: calls.append(kw) or None)
    check_tradingview_connectivity(timeout_s=0.01, max_attempts=1)
    assert calls and calls[0].get("timeout") == 0.01


def test_factory_probe_cancels_pending_future(monkeypatch):
    ok, detail = probe_data_source("tradingview", timeout_s=0.01)
    assert ok is False
    assert "超时" in detail
```

- [ ] **Step 2: 运行测试确认当前第三方调用未传递请求级 timeout**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_data_source_probe_timeout.py -q`

Expected: 模拟调用参数中没有 timeout，或线程在超时后仍保持运行。

- [ ] **Step 3: 传递底层 timeout 并收敛线程生命周期**

为 tvDatafeed/HTTP 客户端使用可配置的连接与读取 timeout；探测函数在超时后调用 `future.cancel()`，并确保 worker 完成后关闭数据源连接。保留 `shutdown(wait=False, cancel_futures=True)` 作为兜底，同时记录残留线程告警。

- [ ] **Step 4: 运行数据源相关测试**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_data_source_probe_timeout.py tests/unit/test_market_defaults.py`

Expected: 探测超时在设定时间内返回，线程池无新增长期存活线程。

- [ ] **Step 5: 提交**

```bash
git add pa_agent/data/tradingview_connectivity.py pa_agent/data/factory.py tests/unit/test_data_source_probe_timeout.py
git commit -m "fix: bound data source probe resources"
```

### Task 5: 关闭窗口时改为非阻塞清理

**Files:**
- Modify: `pa_agent/gui/app_settings_dialog.py:545-565`
- Modify: `pa_agent/gui/main_window.py:4208-4235`
- Test: `tests/unit/test_probe_worker_shutdown.py`

- [ ] **Step 1: 写关闭行为测试**

```python
def test_settings_dialog_close_does_not_wait_ten_seconds(dialog, running_worker, monkeypatch):
    dialog._ds_probe_worker = running_worker
    monkeypatch.setattr(running_worker, "wait", lambda timeout: False)
    elapsed = measure_close_event(dialog)
    assert elapsed < 0.5
    assert running_worker.parent() is None
```

- [ ] **Step 2: 运行测试确认当前 wait(10000) 阻塞**

Run: `QT_QPA_PLATFORM=offscreen .venv-review/bin/python -m pytest -q tests/unit/test_probe_worker_shutdown.py -q`

Expected: 当前实现调用 10 秒等待路径。

- [ ] **Step 3: 移除 UI 线程长等待**

关闭事件只发送 `requestInterruption()`、解除 parent 并连接 `finished -> deleteLater`，立即继续关闭；worker 内部必须在每次重试/网络调用前检查中断标志。

- [ ] **Step 4: 运行 Qt 关闭和主窗口测试**

Run: `QT_QPA_PLATFORM=offscreen .venv-review/bin/python -m pytest -q tests/unit/test_probe_worker_shutdown.py tests/unit/test_main_window_analysis_errors.py`

Expected: 关闭耗时小于 0.5 秒且无 Qt 对象访问异常。

- [ ] **Step 5: 提交**

```bash
git add pa_agent/gui/app_settings_dialog.py pa_agent/gui/main_window.py tests/unit/test_probe_worker_shutdown.py
git commit -m "fix: avoid blocking UI during probe shutdown"
```

### Task 6: 清理并隔离明文凭据

**Files:**
- Modify: `config/settings.json`
- Inspect: `config/settings.json.contaminated`, `.gitignore`, 打包配置文件
- Test: `tests/unit/test_credential_storage.py`

- [ ] **Step 1: 增加凭据泄露检查**

```python
def test_saved_settings_never_persist_provider_or_feishu_secrets(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(provider={"api_key": "k"}, feishu={"app_secret": "s"}), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["provider"]["api_key"] == ""
    assert data["feishu"]["app_secret"] == ""
```

- [ ] **Step 2: 运行测试确认当前保存路径**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_credential_storage.py -q`

Expected: provider key 已被清空；Feishu secret 若仍写入则测试失败。

- [ ] **Step 3: 修复配置和发布边界**

将本地 `config/settings.json` 中真实 `app_secret` 清空并要求轮换；确保 `.gitignore`、打包清单和示例配置只包含空值或占位符。对 `settings.json.contaminated` 做同样检查，必要时移出发布目录但不删除用户数据。

- [ ] **Step 4: 扫描仓库确认无明文凭据**

Run: `rg -n --hidden --glob '!\.git/**' 'app_secret|api_key|webhook_url' config pa_agent tests`

Expected: 只出现空值、占位符或测试 fixture，不出现可用密钥。

- [ ] **Step 5: 提交**

```bash
git add config/settings.json .gitignore tests/unit/test_credential_storage.py
git commit -m "security: isolate application credentials"
```

### Task 7: 原子保存设置并保留备份

**Files:**
- Modify: `pa_agent/config/settings.py:430-455`
- Test: `tests/unit/test_settings_atomic_save.py`

- [ ] **Step 1: 写失败测试**

```python
def test_save_settings_replaces_file_atomically(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text('{"old": true}', encoding="utf-8")
    settings = Settings()
    save_settings(settings, path)
    assert json.loads(path.read_text(encoding="utf-8"))["provider"]["api_key"] == ""
    assert path.with_suffix(".json.bak").exists()
```

- [ ] **Step 2: 运行测试确认当前无备份且直接覆盖**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_settings_atomic_save.py -q`

Expected: `.bak` 文件不存在。

- [ ] **Step 3: 使用临时文件和 os.replace**

写入同目录临时文件，`flush()` 后调用 `os.fsync()`，将旧文件复制为 `.bak`，最后用 `os.replace(temp, path)` 完成原子替换；异常时删除临时文件并保留旧配置。

- [ ] **Step 4: 运行全部设置测试**

Run: `.venv-review/bin/python -m pytest -q tests/unit/test_settings_atomic_save.py tests/unit/test_settings_recovery.py tests/unit/test_settings*.py`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add pa_agent/config/settings.py tests/unit/test_settings_atomic_save.py
git commit -m "fix: atomically persist settings"
```

### Task 8: 同步旧测试契约并建立回归门禁

**Files:**
- Modify: `tests/unit/test_decision_nodes_judges.py`
- Modify: `tests/unit/test_decision_panel.py`
- Modify: `tests/unit/test_free_chat_*.py`
- Modify: `tests/unit/test_market_defaults.py`
- Modify: `tests/unit/test_provider_override_by_model.py`
- Modify: `tests/unit/test_validation_lenient_fixes.py`

- [ ] **Step 1: 按当前实现逐项更新断言**

删除对已移除 `_prediction_group` 等成员的引用；更新 Cursor SDK route、thinking 参数、行情默认值和枚举映射断言。每个变更保留一个针对当前产品行为的正向断言。

- [ ] **Step 2: 运行完整单元测试**

Run: `QT_QPA_PLATFORM=offscreen .venv-review/bin/python -m pytest -q tests/unit`

Expected: 无失败；若仍失败，按错误分类回到对应任务修复，不降低断言强度。

- [ ] **Step 3: 运行最终静态检查**

Run: `.venv-review/bin/python -m compileall -q pa_agent tests && .venv-review/bin/python -m ruff check pa_agent --select F,E9 && git diff --check`

Expected: 编译、lint 通过；`git diff --check` 无新增空白错误。

- [ ] **Step 4: 提交测试契约同步**

```bash
git add tests/unit
git commit -m "test: align unit tests with current contracts"
```

## 执行顺序与验收

按 Task 1 到 Task 8 顺序逐项执行。Task 1-3 解决用户可见的崩溃和错误提示，Task 4-5 解决资源与 UI 生命周期，Task 6-7 解决安全和持久化可靠性，Task 8 最后恢复完整测试门禁。每个任务独立提交，便于回滚和定位回归；最终验收标准是完整单元测试、编译检查和 Ruff 全部通过。

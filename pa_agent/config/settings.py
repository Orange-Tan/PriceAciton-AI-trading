"""Pydantic settings models for PA Agent."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_KEYRING_SERVICE = "pa-agent"
_KEYRING_USERNAME = "provider_api_key"
logger = logging.getLogger(__name__)
_keyring_cached_value: str | None = None
_keyring_route_cached_values: dict[str, str] = {}


def _keyring_username_for_provider(provider: object) -> str:
    """Return a stable credential slot for the selected API route.

    Gateway and SDK routes carry credentials that are unrelated to the normal
    OpenAI-compatible provider key. Keeping separate slots prevents a route
    sync on startup from silently replacing the user's regular API key.
    """
    if isinstance(provider, dict):
        raw_model = provider.get("model", "")
    else:
        raw_model = getattr(provider, "model", "")
    model = str(raw_model or "")
    model = model.strip().lower()
    if model == "openclaw" or model.startswith("openclaw/"):
        return f"{_KEYRING_USERNAME}:qclaw"
    if model == "openclaw_wb" or model.startswith("openclaw_wb/"):
        return f"{_KEYRING_USERNAME}:workbuddy"
    if model == "openclaw_cs" or model.startswith("openclaw_cs/"):
        return f"{_KEYRING_USERNAME}:cursor"
    return _KEYRING_USERNAME


def _keyring_get(username: str = _KEYRING_USERNAME) -> str:
    global _keyring_cached_value
    if username == _KEYRING_USERNAME and _keyring_cached_value is not None:
        return _keyring_cached_value
    if username != _KEYRING_USERNAME and username in _keyring_route_cached_values:
        return _keyring_route_cached_values[username]
    try:
        import keyring  # type: ignore[import]

        value = (keyring.get_password(_KEYRING_SERVICE, username) or "").strip()
        if username == _KEYRING_USERNAME:
            _keyring_cached_value = value
        else:
            _keyring_route_cached_values[username] = value
        return value
    except Exception as exc:  # noqa: BLE001
        logger.debug("Unable to read API key from OS credential store: %s", exc)
        return ""


def _keyring_set(value: str, username: str = _KEYRING_USERNAME) -> bool:
    global _keyring_cached_value
    value = value.strip()
    if username == _KEYRING_USERNAME and _keyring_cached_value == value:
        return True
    if username != _KEYRING_USERNAME and _keyring_route_cached_values.get(username) == value:
        return True
    try:
        import keyring  # type: ignore[import]

        if value:
            keyring.set_password(_KEYRING_SERVICE, username, value)
        else:
            try:
                keyring.delete_password(_KEYRING_SERVICE, username)
            except Exception:
                pass
        if username == _KEYRING_USERNAME:
            _keyring_cached_value = value
        else:
            _keyring_route_cached_values[username] = value
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to write API key to OS credential store: %s", exc)
        return False


DecisionStance = Literal["conservative", "balanced", "aggressive", "extreme_aggressive"]
DataSourceKind = Literal["tradingview", "akshare", "eastmoney", "tushare", "tdx", "tencent"]
NormalizationMode = Literal["strict", "lenient"]
#: 软件显示风格（深灰 / 浅色）
ThemeKind = Literal["dark_gray", "light"]


class AIProviderSettings(BaseModel):
    """AI provider connection and behaviour settings."""

    model_config = ConfigDict(extra="ignore")

    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    api_key_encrypted: str = ""
    thinking: bool = True
    reasoning_effort: Literal["low", "medium", "high", "max"] = "high"
    context_window: int = 2_000_000


class PromptSettings(BaseModel):
    """Prompt assembly tuning (accuracy-oriented defaults)."""

    model_config = ConfigDict(extra="ignore")

    #: When True, Stage 2 loads every strategy .txt (legacy/test behaviour).
    stage2_load_full_strategy_library: bool = False
    experience_max_entries: int = Field(default=0, ge=0, le=10)
    experience_max_chars_per_entry: int = Field(default=400, ge=100, le=4000)
    #: Inject pattern判定表 + 速查 brief into Stage 1 user prompt (reduces missed tags).
    stage1_inject_pattern_briefs: bool = True


class ValidationSettings(BaseModel):
    """Post-LLM validation behaviour."""

    model_config = ConfigDict(extra="ignore")

    normalization_mode: NormalizationMode = "lenient"
    #: Stage-1 cross-field checks (gate trace, bar_by_bar, pattern tags). Off by default.
    stage1_coherence_checks: bool = False
    #: Stage-2 trace / diagnosis cross-checks (not order safety). Off by default.
    stage2_coherence_checks: bool = False
    trace_semantic_checks: bool = False
    strict_bar_by_bar_features: bool = False
    #: Allow Stage 1 truncated JSON tail repair before failing syntax validation.
    disable_truncation_repair: bool = False
    #: Re-call API with structured feedback when validation fails (format errors).
    retry_enabled: bool = True
    retry_max: int = Field(default=3, ge=0, le=5)
    #: Max retries for category=c semantic errors (subset only).
    retry_max_semantic: int = Field(default=1, ge=0, le=3)
    retry_stage2: bool = True


class GeneralSettings(BaseModel):
    """UI and data-feed general settings."""

    model_config = ConfigDict(extra="ignore")

    analysis_bar_count: int = Field(default=100, ge=2, le=5000)
    refresh_interval_ms: int = 1000
    context_warning_threshold_pct: float = 80.0
    #: 软件显示风格：浅色（默认）/ 深灰，应用启动与切换时全局生效
    theme: ThemeKind = "light"
    last_data_source: DataSourceKind = "tradingview"
    #: A-share K-line adjust for East Money / Baostock (qfq=前复权)
    kline_adjust: Literal["qfq", "hfq", "none"] = "qfq"
    #: TradingView 交易所；空字符串 =（自动）依次探测预设列表
    last_tradingview_exchange: str = ""
    last_symbol: str = "XAUUSD"
    last_timeframe: str = "15m"
    decision_flow_auto_play: bool = True
    decision_flow_play_seconds: int = 50
    #: 阶段二给出限价/突破/市价单时：警报音、弹窗，并自动切到「决策」页（跳过决策树可视化演示）
    alert_on_order_opportunity: bool = True
    incremental_max_new_bars: int = Field(default=10, ge=0, le=500)
    #: 阶段二交易倾向：balanced=默认；conservative/aggressive 逐级调整下单意愿
    decision_stance: DecisionStance = "balanced"
    #: 决策树可视化：在「整图适配」基础上的缩放百分比（100=与适配一致；可任意放大，仅下限 10%）
    decision_flow_default_zoom_pct: int = Field(default=600, ge=10)
    #: 「实时」页思考过程/撰写回答框与追问输入框的等宽字体字号（pt）
    stream_pane_font_pt: int = Field(default=11, ge=8, le=28)
    #: K 线图上 #序号 标签的字号（pt）
    chart_seq_label_font_pt: int = Field(default=11, ge=6, le=24)
    #: 两阶段分析结束后是否自动恢复 K 线图表实时刷新
    auto_resume_chart_after_analysis: bool = False
    #: 持续跟踪分析：有新K线收盘时自动触发新一轮分析
    keep_analysis: bool = False
    #: 重试后取消持续跟踪分析：校验失败触发重试后自动关闭 keep_analysis
    cancel_keep_analysis_on_retry: bool = False
    #: 交易决策置信度门槛：仅当 trade_confidence >= 此值时，才视为有下单机会（弹窗警报并提供决策详情）
    decision_confidence_threshold: int = Field(default=40, ge=0, le=100)
    #: 开启下根K线预期功能；关闭时不向模型请求该预测，节省 token
    enable_next_bar_prediction: bool = False
    #: 同一结构位 entry 相差≤3跳时，禁止反向新方案的冷却 K 线根数（已收盘）
    structure_flip_cooldown_bars: int = Field(default=3, ge=1, le=50)
    #: 左侧「自选股」栏列表（6位A股代码 / 指数，或 TradingView 品种名）
    watchlist: list[str] = Field(default_factory=lambda: ["sh000001", "sz399001", "sz399006"])
    #: 左侧「自选股」板块及其品种归属
    watchlist_groups: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "全部": ["sh000001", "sz399001", "sz399006"],
            "持仓": [],
            "美股": [],
            "港股": [],
        }
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_watchlist_groups(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        from pa_agent.config.watchlist_store import migrate_watchlist

        data = dict(data)
        data["watchlist_groups"] = migrate_watchlist(
            data.get("watchlist_groups"), data.get("watchlist")
        )
        return data

    @field_validator("watchlist", mode="before")
    @classmethod
    def _coerce_watchlist(cls, v: object) -> object:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        out: list[str] = []
        seen: set[str] = set()
        for s in v or []:
            if s is None:
                continue
            s = (str(s) or "").strip()
            if s and s not in seen:
                out.append(s)
                seen.add(s)
        return out

    @field_validator("last_data_source", mode="before")
    @classmethod
    def _coerce_legacy_data_source(cls, v: object) -> object:
        if v in ("adata", "a_share"):
            return "akshare"
        if v in ("eastmoney",):
            return "eastmoney"
        if v in ("tushare",):
            return "tushare"
        # 已移除的 mt5/yfinance → 回退为默认 TradingView
        if v in ("mt5", "yfinance"):
            return "tradingview"
        return v

    @field_validator("decision_flow_default_zoom_pct", mode="before")
    @classmethod
    def _coerce_zoom_pct(cls, v: object) -> object:
        if v is None:
            return 50
        return v


_FEISHU_CONFIG_KEYS = (
    "enabled",
    "webhook_url",
    "secret",
    "app_id",
    "app_secret",
    "notify_on_order_only",
    "bound_open_id",
    "bound_name",
    "bound_tenant_brand",
)


class FeishuSettings(BaseModel):
    """Feishu bot notification settings (persisted in settings.json)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    webhook_url: str = ""
    secret: str = ""
    app_id: str = ""
    app_secret: str = ""
    #: True = only push when there is an order opportunity.
    notify_on_order_only: bool = True
    #: 扫码一键创建机器人后绑定的单聊目标（用户 open_id），消息经
    #: ``im/v1/messages`` 推送到手机飞书「与机器人的单聊」。
    bound_open_id: str = ""
    #: 绑定用户的展示名（可选，仅用于界面提示）。
    bound_name: str = ""
    #: 绑定来源品牌："feishu"（国内）或 "lark"（国际版）。
    bound_tenant_brand: str = "feishu"


class TushareSettings(BaseModel):
    """Tushare Pro data source settings (persisted in ignored settings.json)."""

    model_config = ConfigDict(extra="ignore")

    token: str = ""


class PushPlusSettings(BaseModel):
    """PushPlus notification settings (settings.json only; no GUI)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    token: str = ""


class Settings(BaseModel):
    """Root settings object persisted to config/settings.json."""

    model_config = ConfigDict(extra="ignore")

    provider: AIProviderSettings = Field(default_factory=AIProviderSettings)
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    prompt: PromptSettings = Field(default_factory=PromptSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    feishu: FeishuSettings = Field(default_factory=FeishuSettings)
    pushplus: PushPlusSettings = Field(default_factory=PushPlusSettings)
    tushare: TushareSettings = Field(default_factory=TushareSettings)


def provider_api_key_configured(settings: Settings | None) -> bool:
    """Return True when a non-empty API key is loaded in memory."""
    if settings is None:
        return False
    return bool((settings.provider.api_key or "").strip())


# ── Persistence ───────────────────────────────────────────────────────────────


def _migrate_legacy_feishu_json(raw: dict, settings_path: Path) -> bool:
    """Merge legacy config/feishu.json into settings.feishu when needed."""
    legacy_path = settings_path.parent / "feishu.json"
    if not legacy_path.exists():
        return False

    feishu = raw.setdefault("feishu", {})
    if (feishu.get("webhook_url") or "").strip():
        return False

    try:
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("legacy feishu.json unreadable (%s); skipping migration", exc)
        return False

    migrated = False
    for key in _FEISHU_CONFIG_KEYS:
        if key not in legacy:
            continue
        value = legacy.get(key)
        if value in (None, ""):
            continue
        if feishu.get(key) in (None, ""):
            feishu[key] = value
            migrated = True
    if migrated:
        logger.info("Migrated Feishu config from %s into settings.json", legacy_path)
    return migrated


def load_settings(path: Path | None = None) -> Settings:
    """Load settings from *path* (default: SETTINGS_JSON_PATH).

    Returns default Settings and writes them to disk if the file is absent.
    """
    from pa_agent.config.paths import SETTINGS_JSON_PATH

    path = path or SETTINGS_JSON_PATH

    if not path.exists():
        defaults = Settings()
        save_settings(defaults, path)
        return defaults

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("settings.json unreadable (%s); using defaults", exc)
        return Settings()

    if not isinstance(raw, dict):
        logger.warning(
            "settings.json has invalid root type %s; using defaults",
            type(raw).__name__,
        )
        return Settings()

    # Migrate legacy field names
    general = raw.get("general", {})
    if not isinstance(general, dict):
        logger.warning("settings.general has invalid type; using defaults for general")
        general = {}
    # 深蓝主题已移除，旧配置回退为默认浅色
    if general.get("theme") == "dark_blue":
        general["theme"] = "light"
    if "cost_warning_threshold_pct" in general and "context_warning_threshold_pct" not in general:
        general["context_warning_threshold_pct"] = general.pop("cost_warning_threshold_pct")
    general.pop("last_htf_text", None)
    from pa_agent.data.market_defaults import migrate_general_gold_defaults

    migrate_general_gold_defaults(general)
    if "default_bar_count" in general and "analysis_bar_count" not in general:
        general["analysis_bar_count"] = general.pop("default_bar_count")
    raw["general"] = general
    provider = raw.get("provider", {})
    if not isinstance(provider, dict):
        logger.warning("settings.provider has invalid type; using defaults for provider")
        provider = {}
    provider.pop("pricing", None)
    raw["provider"] = provider

    provider = raw.setdefault("provider", {})
    # API keys are kept in the OS credential store; migrate any legacy plaintext
    # value once, then ensure it is never written back to settings.json.
    keyring_username = _keyring_username_for_provider(provider)
    stored_key = _keyring_get(keyring_username)
    plaintext_key = str(provider.get("api_key") or "").strip()
    migrated_key = False
    if plaintext_key and plaintext_key != stored_key:
        stored_key = plaintext_key
        migrated_key = _keyring_set(plaintext_key, keyring_username)
    provider["api_key"] = stored_key
    provider.pop("api_key_encrypted", None)

    migrated_feishu = _migrate_legacy_feishu_json(raw, path)
    try:
        settings = Settings.model_validate(raw)
    except ValidationError as exc:
        invalid_path = path.with_name(f"{path.name}.invalid")
        try:
            if invalid_path.exists():
                invalid_path = path.with_name(f"{path.name}.{int(time.time())}.invalid")
            invalid_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as backup_exc:
            logger.warning("Unable to quarantine invalid settings: %s", backup_exc)
        fields = ", ".join(str(error.get("loc", "<root>")) for error in exc.errors()[:5])
        logger.warning("settings.json validation failed (%s); using defaults", fields)
        defaults = Settings()
        try:
            save_settings(defaults, path)
        except (OSError, RuntimeError) as save_exc:
            logger.warning("Unable to persist default settings: %s", save_exc)
        return defaults
    dirty = migrated_feishu or migrated_key
    if settings.pushplus.enabled and not settings.pushplus.token.strip():
        if not (os.environ.get("PUSHPLUS_TOKEN") or "").strip():
            settings.pushplus.enabled = False
            logger.info(
                "PushPlus enabled but token empty — auto-disabled "
                "(Feishu notifications unaffected)"
            )
            dirty = True
    if dirty:
        save_settings(settings, path)
    return settings


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Persist settings to *path* (default: SETTINGS_JSON_PATH)."""
    from pa_agent.config.paths import SETTINGS_JSON_PATH

    path = path or SETTINGS_JSON_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    api_key = (settings.provider.api_key or "").strip()
    keyring_username = _keyring_username_for_provider(settings.provider)
    if api_key and not _keyring_set(api_key, keyring_username):
        raise RuntimeError("无法将 API Key 保存到系统凭据库")
    if not api_key:
        cached = (
            _keyring_cached_value
            if keyring_username == _KEYRING_USERNAME
            else _keyring_route_cached_values.get(keyring_username)
        )
        if cached:
            _keyring_set("", keyring_username)
    data = settings.model_dump()
    data.setdefault("provider", {})["api_key"] = ""
    data["provider"].pop("api_key_encrypted", None)
    # Feishu app credentials are runtime-only; never persist them in plaintext.
    feishu_data = data.get("feishu")
    if isinstance(feishu_data, dict):
        feishu_data["app_secret"] = ""
        feishu_data["secret"] = ""

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            backup = path.with_name(f"{path.name}.bak")
            try:
                backup.write_bytes(path.read_bytes())
            except OSError as exc:
                logger.warning("Unable to back up settings before replace: %s", exc)
        os.replace(temp_name, path)
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass

"""Model provider presets for the settings dialog.

Catalogs OpenAI plus five leading domestic (China) model vendors.  Each entry
is an OpenAI-compatible endpoint so it plugs into :class:`DeepSeekClient`
unchanged (``base_url`` + ``model`` + ``api_key``).

Model ids are editable in the UI — the lists here are convenient defaults, not
an exhaustive catalog.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProviderPreset:
    """A ready-to-use OpenAI-compatible model vendor."""

    id: str
    name: str                                  # 中文展示名
    vendor: str                                # 英文厂商名
    base_url: str
    models: tuple[tuple[str, str], ...]        # (model_id, 简短说明)
    api_key_url: str                           # 获取 API Key 的入口
    thinking_default: bool = True


#: Ordered provider catalog shown in the settings dialog.
PROVIDERS: tuple[ModelProviderPreset, ...] = (
    ModelProviderPreset(
        id="deepseek",
        name="深度求索 DeepSeek",
        vendor="DeepSeek",
        base_url="https://api.deepseek.com",
        models=(
            ("deepseek-v4-flash", "默认 · 快"),
            ("deepseek-v4-pro", "旗舰 · 强"),
            ("deepseek-chat", "对话 · 快"),
            ("deepseek-reasoner", "推理 · 慢"),
        ),
        api_key_url="https://platform.deepseek.com/api_keys",
        thinking_default=True,
    ),
    ModelProviderPreset(
        id="openai",
        name="OpenAI",
        vendor="OpenAI",
        base_url="https://api.openai.com/v1",
        models=(
            ("gpt-4o", "多模态 · 均衡"),
            ("gpt-4o-mini", "轻量 · 快"),
            ("gpt-4.1", "长上下文"),
            ("gpt-4.1-mini", "轻量长上下文"),
            ("o3-mini", "推理 · 快"),
            ("o4-mini", "推理 · 强"),
        ),
        api_key_url="https://platform.openai.com/api-keys",
        thinking_default=False,
    ),
    ModelProviderPreset(
        id="zhipu",
        name="智谱 AI（GLM）",
        vendor="Zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        models=(
            ("glm-4-plus", "旗舰 · 强"),
            ("glm-4-air", "均衡 · 快"),
            ("glm-4-flash", "轻量 · 免费"),
            ("glm-4-long", "长上下文"),
        ),
        api_key_url="https://open.bigmodel.cn/usercenter/apikeys",
        thinking_default=True,
    ),
    ModelProviderPreset(
        id="moonshot",
        name="月之暗面 Kimi",
        vendor="Moonshot",
        base_url="https://api.moonshot.cn/v1",
        models=(
            ("moonshot-v1-8k", "短文本 · 快"),
            ("moonshot-v1-32k", "标准"),
            ("moonshot-v1-128k", "长文本"),
            ("kimi-k2-0711-preview", "推理 · 强"),
        ),
        api_key_url="https://platform.moonshot.cn/console/api-keys",
        thinking_default=True,
    ),
    ModelProviderPreset(
        id="qwen",
        name="阿里 通义千问",
        vendor="Alibaba",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=(
            ("qwen-max", "旗舰 · 强"),
            ("qwen-plus", "均衡"),
            ("qwen-turbo", "轻量 · 快"),
            ("qwen-long", "长上下文"),
        ),
        api_key_url="https://bailian.console.aliyun.com/?apiKey=1",
        thinking_default=True,
    ),
    ModelProviderPreset(
        id="doubao",
        name="字节 豆包",
        vendor="ByteDance",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        models=(
            ("doubao-1-5-pro-32k-250115", "Pro · 强"),
            ("doubao-1-5-lite-32k-250115", "Lite · 快"),
            ("doubao-seed-1-6-250615", "Seed 推理"),
        ),
        api_key_url="https://console.volcengine.com/ark",
        thinking_default=True,
    ),
)

_PROVIDER_BY_ID: dict[str, ModelProviderPreset] = {p.id: p for p in PROVIDERS}

#: keyword → provider id, used when the base_url is a custom relay but the
#: model id still identifies the vendor.
_MODEL_KEYWORD_TO_PROVIDER: dict[str, str] = {
    "deepseek": "deepseek",
    "glm": "zhipu",
    "moonshot": "moonshot",
    "kimi": "moonshot",
    "qwen": "qwen",
    "doubao": "doubao",
    "gpt-": "openai",
    "o3": "openai",
    "o4": "openai",
}


def provider_presets() -> tuple[ModelProviderPreset, ...]:
    """Return the ordered provider catalog."""
    return PROVIDERS


def find_provider(preset_id: str | None) -> ModelProviderPreset | None:
    """Return the preset for *preset_id*, or None."""
    if not preset_id:
        return None
    return _PROVIDER_BY_ID.get(preset_id)


def guess_provider(base_url: str, model: str = "") -> str | None:
    """Best-effort mapping of the current (base_url, model) to a preset id.

    Returns None when nothing matches — the dialog then falls back to the
    "自定义" entry so the user's hand-written provider is preserved.
    """
    b = (base_url or "").strip().lower()
    if b:
        for preset in PROVIDERS:
            if preset.base_url.lower() in b:
                return preset.id

    m = (model or "").strip().lower()
    if m:
        for preset in PROVIDERS:
            for model_id, _ in preset.models:
                if m == model_id.lower():
                    return preset.id
        for keyword, pid in _MODEL_KEYWORD_TO_PROVIDER.items():
            if keyword in m:
                return pid
    return None

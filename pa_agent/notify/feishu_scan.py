"""飞书「扫码一键创建机器人并绑定」— OAuth 2.0 Device Authorization Grant (RFC 8628).

对齐飞书官方 SDK ``registerApp`` / 官方 CLI ``app_registration`` 的实现：

1. ``begin_registration()``
   ``POST https://accounts.feishu.cn/oauth/v1/app/registration``（``action=begin``），
   返回 ``device_code`` / ``user_code``，并据此拼出扫码确认链接。
2. 用户用手机飞书扫码打开确认链接，确认后手机端自动创建带机器人能力的应用
   （权限与事件订阅已预置，含 ``im:message:send_as_bot``），并把该机器人
   添加到与用户本人的单聊——这就是「手机端自动创建机器人」。
3. ``poll_registration()``
   轮询同一端点（``action=poll``），直到返回 ``client_id`` / ``client_secret``
   以及扫码用户的 ``open_id``。之后推送消息时用 ``im/v1/messages``
   （``receive_id_type=open_id``）把信号直接发到手机飞书的机器人单聊里。

协议参考来源（larksuite/cli 官方源码）：
  internal/auth/app_registration.go / device_flow.go / paths.go
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event
from typing import Callable
from urllib.parse import quote

import requests  # type: ignore[import]

logger = logging.getLogger(__name__)

# ── 端点 ────────────────────────────────────────────────────────────────────────
_FEISHU_ACCOUNTS = "https://accounts.feishu.cn"
_FEISHU_OPEN = "https://open.feishu.cn"
_LARK_ACCOUNTS = "https://accounts.larksuite.com"
_LARK_OPEN = "https://open.larksuite.com"

_REGISTRATION_PATH = "/oauth/v1/app/registration"
#: 扫码确认页（用户手机飞书打开，user_code 与之配对）。
_REGISTRATION_PAGE = "https://open.feishu.cn/page/launcher"

_REG_BEGIN_TIMEOUT_S = 30
_REG_POLL_TIMEOUT_S = 15
_MAX_POLL_INTERVAL_S = 60
#: 扫码后需要返回的用户信息作用域（与飞书官方 CLI 一致）。
#: 注意：API 仅接受单个作用域或 ``open_id tenant_brand`` 组合；
#: 曾传入 ``open_id tenant_brand name``（多出 ``name``）会被拒绝（code 20103）。
_REQUEST_USER_INFO = "open_id tenant_brand"


@dataclass
class BeginInfo:
    """begin 响应：用于展示二维码 + 后续轮询。"""

    device_code: str
    user_code: str
    verification_url: str
    interval: int
    expires_in: int


@dataclass
class RegistrationResult:
    """绑定成功：应用凭据 + 扫码用户的 open_id。"""

    client_id: str
    client_secret: str
    open_id: str
    tenant_brand: str
    name: str


def _error_text(data: dict) -> str:
    return str(
        data.get("error_description")
        or data.get("error")
        or data.get("msg")
        or "未知错误"
    )


def begin_registration() -> BeginInfo:
    """发起一次扫码注册，返回二维码链接与轮询参数。

    Raises
    ------
    RuntimeError
        网络/协议错误或响应缺少 device_code。
    """
    form = {
        "action": "begin",
        "archetype": "PersonalAgent",
        "auth_method": "client_secret",
        "request_user_info": _REQUEST_USER_INFO,
    }
    resp = requests.post(
        _FEISHU_ACCOUNTS + _REGISTRATION_PATH,
        data=form,
        timeout=_REG_BEGIN_TIMEOUT_S,
    )
    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"begin 响应非 JSON（HTTP {resp.status_code}）") from exc

    if resp.status_code >= 400 or data.get("error"):
        raise RuntimeError(f"发起扫码注册失败：{_error_text(data)}")

    device_code = data.get("device_code") or ""
    if not device_code:
        raise RuntimeError("发起扫码注册失败：响应缺少 device_code")

    user_code = data.get("user_code") or ""
    try:
        expires_in = int(data.get("expire_in") or data.get("expires_in") or 600)
        interval = int(data.get("interval") or 5)
    except (TypeError, ValueError):
        expires_in, interval = 600, 5

    verification_url = (
        f"{_REGISTRATION_PAGE}?user_code={quote(user_code)}"
        f"&from=sdk&source=pa-agent&tp=sdk"
    )
    logger.info(
        "飞书扫码注册已发起 device_code=%s… user_code=%s",
        device_code[:8],
        user_code,
    )
    return BeginInfo(
        device_code=device_code,
        user_code=user_code,
        verification_url=verification_url,
        interval=max(1, interval),
        expires_in=max(60, expires_in),
    )


def poll_registration(
    info: BeginInfo,
    *,
    stop_event: Event | None = None,
    on_status: Callable[[str], None] | None = None,
) -> RegistrationResult | None:
    """轮询扫码确认结果，直到成功、拒绝、过期或被取消。

    Parameters
    ----------
    stop_event:
        设置后立即中止并返回 None（用户取消）。
    on_status:
        进度回调（"等待扫码确认…" 等），用于 GUI 状态栏。

    Returns
    -------
    RegistrationResult
        绑定成功；取消返回 None。

    Raises
    ------
    RuntimeError
        用户拒绝 / 二维码过期 / 超时 / 网络持续失败。
    """
    url = _FEISHU_ACCOUNTS + _REGISTRATION_PATH
    interval = max(1, info.interval)
    deadline = time.monotonic() + info.expires_in
    attempts = 0

    def _should_stop() -> bool:
        return stop_event is not None and stop_event.is_set()

    while time.monotonic() < deadline:
        if _should_stop():
            return None
        time.sleep(interval)
        if _should_stop():
            return None

        attempts += 1
        try:
            resp = requests.post(
                url,
                data={"action": "poll", "device_code": info.device_code},
                timeout=_REG_POLL_TIMEOUT_S,
            )
            data = resp.json()
        except Exception as exc:  # 网络抖动：退避后重试
            if on_status:
                on_status(f"网络异常，重试中…（{exc}）")
            interval = min(interval + 1, _MAX_POLL_INTERVAL_S)
            continue

        user_info = data.get("user_info") or {}
        tenant_brand = user_info.get("tenant_brand") or ""
        # 国际 Lark 租户：切换到 larksuite 域继续轮询（同 device_code）。
        if tenant_brand == "lark" and url.startswith(_FEISHU_ACCOUNTS):
            url = _LARK_ACCOUNTS + _REGISTRATION_PATH
            if on_status:
                on_status("检测到国际版 Lark 租户，已切换认证域…")
            continue

        error = data.get("error")
        if error:
            if error == "authorization_pending":
                if on_status:
                    on_status("等待扫码确认…")
                continue
            if error == "slow_down":
                interval = min(interval + 5, _MAX_POLL_INTERVAL_S)
                continue
            if error == "access_denied":
                raise RuntimeError("用户在手机上拒绝了授权")
            if error in ("expired_token", "invalid_grant"):
                raise RuntimeError("二维码已过期，请重新发起")
            raise RuntimeError(_error_text(data))

        client_id = data.get("client_id") or ""
        client_secret = data.get("client_secret") or ""
        if client_id and client_secret:
            result = RegistrationResult(
                client_id=client_id,
                client_secret=client_secret,
                open_id=user_info.get("open_id") or "",
                tenant_brand=tenant_brand or "feishu",
                name=user_info.get("name")
                or user_info.get("display_name")
                or "",
            )
            logger.info(
                "飞书扫码绑定成功 app=%s… user=%s brand=%s",
                client_id[:10],
                result.open_id[:8] if result.open_id else "?",
                result.tenant_brand,
            )
            return result
        # 无 error 但凭据不完整：继续轮询

    raise RuntimeError("绑定超时，请重新发起")

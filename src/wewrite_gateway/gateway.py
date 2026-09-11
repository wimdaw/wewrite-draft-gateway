"""wx-draft-worker 网关的 HTTP 客户端。

对接接口（详见 wx-draft-worker 的 API.md）：

    GET    /api/health          健康检查（无需鉴权）
    POST   /api/draft           新建草稿        ← 本适配器的主路径
    GET    /api/drafts          草稿列表（核对用）
    DELETE /api/drafts/:id      删除草稿

鉴权：请求头 ``X-API-Key: wxk_xxx``（网关同时兼容 ``?key=`` 与 ``Authorization: Bearer``）。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import Settings

# 微信 / Cloudflare 常见错误的通俗解释（命中即附加到异常信息）
ERROR_HINTS: dict[str, str] = {
    "40164": "IP 不在白名单：把 Cloudflare 全部出口 IPv4 段加入公众号后台的 IP 白名单",
    "40001": "AppSecret 无效：到网关后台「公众号管理」重新保存该账号",
    "40013": "AppID 无效：检查后台「公众号管理」里填的 AppID",
    "45009": "微信接口调用超限，稍后重试（网关已做 token 缓存）",
    "53500": "该公众号没有草稿接口权限，需已认证的公众号",
    "48001": "接口未授权：未认证账号不支持该能力",
    "1010": "被 Cloudflare 边缘拦截（Bot 检测）：请求需带浏览器 User-Agent",
    "尚未添加公众号": "还没在网关后台「公众号管理」添加 AppID / AppSecret，或未设为默认",
    "无法生成封面": "封面缺失：传 --cover 指定本地图，或保证正文里至少有一张图片",
}


class GatewayError(RuntimeError):
    """网关返回失败、或网络不可达。"""

    def __init__(self, message: str, *, status: int = 0, payload: Any = None):
        self.status = status
        self.payload = payload
        hint = ""
        for code, text in ERROR_HINTS.items():
            if code in message:
                hint = f"\n可能原因：{text}"
                break
        if not hint and status == 401:
            hint = "\n可能原因：令牌无效/已停用 —— 到网关后台「令牌管理」确认，或运行 `wewrite-push doctor`"
        super().__init__(message + hint)


class GatewayClient:
    """带重试与中文错误解释的轻量客户端。"""

    def __init__(self, settings: Settings, session: Optional[requests.Session] = None):
        self.st = settings
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ utils
    def _headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        head = {
            "X-API-Key": self.st.token,
            "User-Agent": self.st.user_agent,
            "Accept": "application/json",
        }
        if extra:
            head.update(extra)
        return head

    def _request(self, method: str, path: str, *, retries: int = 2,
                 headers: Optional[dict[str, str]] = None, **kw) -> Any:
        if not self.st.url:
            raise GatewayError("未配置网关地址（WX_GATEWAY_URL）")
        url = f"{self.st.url}{path}"
        kw.setdefault("timeout", self.st.timeout)
        kw.setdefault("proxies", self.st.proxies)
        last: Optional[Exception] = None

        for attempt in range(retries + 1):
            try:
                resp = self.session.request(method, url, headers=self._headers(headers), **kw)
            except requests.RequestException as exc:
                last = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise GatewayError(f"请求网关失败：{exc}") from exc

            if resp.status_code >= 500 and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue

            try:
                data = resp.json()
            except ValueError:
                raise GatewayError(
                    f"网关返回非 JSON 内容（HTTP {resp.status_code}）：{resp.text[:200]}",
                    status=resp.status_code,
                )

            if resp.status_code >= 400 or data.get("ok") is False:
                raise GatewayError(
                    f"网关返回失败（HTTP {resp.status_code}）：{data.get('error') or resp.text[:200]}",
                    status=resp.status_code,
                    payload=data,
                )
            return data.get("data", data)

        raise GatewayError(f"请求网关失败：{last}")

    # ----------------------------------------------------------------- public
    def health(self) -> dict[str, Any]:
        """健康检查（不需要令牌）。"""
        return self._request("GET", "/api/health", retries=1)

    def push(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /api/draft —— 新建草稿。"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self._request(
            "POST", "/api/draft",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    def drafts(self, count: int = 10) -> dict[str, Any]:
        """GET /api/drafts —— 草稿列表（推送后核对）。"""
        return self._request("GET", "/api/drafts", params={"count": count}, retries=1)


# --------------------------------------------------------------------- cover
def file_to_data_uri(path: str | Path) -> str:
    """本地封面文件 → data URI（网关支持 data URI 作为 cover）。"""
    p = Path(path)
    if not p.is_file():
        raise GatewayError(f"封面文件不存在：{path}")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    if not mime.startswith("image/"):
        raise GatewayError(f"封面必须是图片：{path}（识别为 {mime}）")
    blob = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{blob}"


def build_payload(article, settings: Settings, *, cover: Optional[str] = None,
                  cover_url: Optional[str] = None, title: Optional[str] = None,
                  digest: Optional[str] = None, author: Optional[str] = None,
                  account_id: Optional[str] = None, source_url: Optional[str] = None,
                  open_comment: Optional[int] = None,
                  only_fans_comment: Optional[int] = None) -> dict[str, Any]:
    """组装 /api/draft 请求体（字段名严格对齐网关 DraftRequest）。"""
    cover_value: Optional[str] = None
    if cover:
        cover_value = file_to_data_uri(cover)
    elif cover_url:
        cover_value = cover_url

    use_html = bool(getattr(article, "html", ""))
    payload: dict[str, Any] = {
        "title": (title or article.title or "未命名文章")[:64],
        "content": article.html if use_html else article.markdown,
        "contentType": "html" if use_html else "markdown",
    }
    auto_digest = digest or getattr(article, "digest", "")
    if auto_digest:
        payload["digest"] = auto_digest[:120]
    author_value = author or settings.default_author
    if author_value:
        payload["author"] = author_value[:8]          # 微信限制作者 ≤ 8 字
    if cover_value:
        payload["cover"] = cover_value
    acc = account_id or settings.account_id
    if acc:
        payload["accountId"] = acc
    if source_url:
        payload["contentSourceUrl"] = source_url
    if open_comment is not None:
        payload["needOpenComment"] = open_comment
    if only_fans_comment is not None:
        payload["onlyFansCanComment"] = only_fans_comment
    return payload


def push_draft(settings: Settings, article, *, client: Optional[GatewayClient] = None,
               dry_run: bool = False, **options) -> dict[str, Any]:
    """把 ``Article`` 推到网关，返回 ``{"media_id": ..., "account": ...}``。

    常用可选项：``cover``（本地图路径）、``cover_url``、``title``、``digest``、
    ``author``、``account_id``、``source_url``、``open_comment``、``only_fans_comment``。
    """
    if not dry_run:
        settings.require()
    payload = build_payload(article, settings, **options)
    if dry_run:
        return {"dry_run": True, "payload": payload}
    cli = client or GatewayClient(settings)
    return cli.push(payload)

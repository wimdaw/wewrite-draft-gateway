"""配置解析：命令行参数 > 环境变量 > .env 文件 > YAML 配置文件。

只需要两样东西：

  * 网关地址 ``WX_GATEWAY_URL``，例如 https://wx-draft-worker.xxx.workers.dev
  * 业务令牌 ``WX_GATEWAY_TOKEN``，形如 ``wxk_xxx``（在网关后台「令牌管理」创建）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 网关在 Cloudflare 上，非浏览器 UA 可能被 Bot 检测拦截（错误码 1010）
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

ENV_URL = "WX_GATEWAY_URL"
ENV_TOKEN = "WX_GATEWAY_TOKEN"
ENV_UA = "WX_GATEWAY_UA"
ENV_ACCOUNT = "WX_GATEWAY_ACCOUNT_ID"
ENV_PROXY = "WX_GATEWAY_PROXY"
ENV_AUTHOR = "WX_GATEWAY_AUTHOR"
ENV_THEME = "WX_GATEWAY_THEME"

# 越靠前的文件优先级越高
ENV_FILES = (
    Path.cwd() / ".env",
    Path.cwd() / ".env.local",
    Path.home() / ".wewrite-gateway.env",
)

YAML_FILES = (
    Path.home() / ".config" / "wewrite-gateway.yaml",
    Path.cwd() / "wewrite-gateway.yaml",
)


class ConfigError(RuntimeError):
    """缺少必需配置。"""


@dataclass
class Settings:
    """一次推送所需的全部设置。"""

    url: str = ""
    token: str = ""
    user_agent: str = DEFAULT_UA
    default_author: Optional[str] = None
    default_theme: Optional[str] = None
    account_id: Optional[str] = None
    proxy: Optional[str] = None
    timeout: int = 180
    source: dict[str, Any] = field(default_factory=dict)   # 每个值来自哪里，供 doctor 展示

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, url: Optional[str] = None, token: Optional[str] = None,
             theme: Optional[str] = None, account_id: Optional[str] = None,
             proxy: Optional[str] = None, timeout: Optional[int] = None) -> "Settings":
        env_file, env_src = _read_dotenv_files()
        yaml_vals = _read_yaml_file()
        src: dict[str, Any] = {}

        def pick(env_key: str, explicit: Optional[str], *fallbacks) -> Optional[str]:
            """按优先级取值，并记录来源。fallbacks 为 (来源说明, 值) 元组。"""
            if explicit:
                src[env_key] = "命令行参数"
                return explicit
            if os.environ.get(env_key):
                src[env_key] = f"环境变量 {env_key}"
                return os.environ[env_key]
            for name, value in fallbacks:
                if value:
                    src[env_key] = name
                    return str(value)
            return None

        st = cls()
        st.url = (pick(ENV_URL, url,
                       (env_src.get(ENV_URL, "本地 .env"), env_file.get(ENV_URL)),
                       ("~/.config/wewrite-gateway.yaml", yaml_vals.get("url"))) or "").rstrip("/")
        st.token = (pick(ENV_TOKEN, token,
                         (env_src.get(ENV_TOKEN, "本地 .env"), env_file.get(ENV_TOKEN)),
                         ("~/.config/wewrite-gateway.yaml", yaml_vals.get("token"))) or "")
        st.user_agent = (pick(ENV_UA, None,
                              (env_src.get(ENV_UA, "本地 .env"), env_file.get(ENV_UA)),
                              ("默认值", DEFAULT_UA)) or DEFAULT_UA)
        st.account_id = pick(ENV_ACCOUNT, account_id,
                             (env_src.get(ENV_ACCOUNT, "本地 .env"), env_file.get(ENV_ACCOUNT)),
                             ("~/.config/wewrite-gateway.yaml", yaml_vals.get("account_id")))
        st.proxy = pick(ENV_PROXY, proxy,
                        (env_src.get(ENV_PROXY, "本地 .env"), env_file.get(ENV_PROXY)),
                        ("~/.config/wewrite-gateway.yaml", yaml_vals.get("proxy")))
        st.default_author = pick(ENV_AUTHOR, None,
                                 (env_src.get(ENV_AUTHOR, "本地 .env"), env_file.get(ENV_AUTHOR)),
                                 ("~/.config/wewrite-gateway.yaml", yaml_vals.get("author")))
        st.default_theme = pick(ENV_THEME, theme,
                                (env_src.get(ENV_THEME, "本地 .env"), env_file.get(ENV_THEME)),
                                ("~/.config/wewrite-gateway.yaml", yaml_vals.get("theme")))
        if timeout:
            st.timeout = int(timeout)
        elif str(env_file.get("WX_GATEWAY_TIMEOUT", "")).isdigit():
            st.timeout = int(env_file["WX_GATEWAY_TIMEOUT"])
        st.source = src
        return st

    # ---------------------------------------------------------------- helpers
    def require(self) -> None:
        """推送前校验必需项，缺失时给出可操作的提示。"""
        missing = []
        if not self.url:
            missing.append(f"{ENV_URL} —— 网关地址，如 https://wx-draft-worker.xxx.workers.dev")
        if not self.token:
            missing.append(f"{ENV_TOKEN} —— 形如 wxk_xxx，在网关后台「令牌管理」创建")
        if missing:
            raise ConfigError(
                "缺少配置：\n  - " + "\n  - ".join(missing) +
                "\n提示：写进项目里的 .env，或设为环境变量；也可运行 `wewrite-push doctor` 查看体检结果。"
            )

    @property
    def proxies(self) -> Optional[dict[str, str]]:
        if not self.proxy:
            return None
        return {"http": self.proxy, "https": self.proxy}


def _label(path: Path) -> str:
    """把配置文件路径写成好认的形式，例如 ~/.wewrite-gateway.env。"""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_dotenv_files() -> tuple[dict[str, str], dict[str, str]]:
    """返回 (键值表, 每个键来自哪个文件)——来源精确到文件，便于 doctor 排查。"""
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    for path in reversed(ENV_FILES):        # 倒序覆盖，保证靠前的文件优先级更高
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                values[key] = val.strip().strip('"').strip("'")
                sources[key] = _label(path)
        except OSError:
            continue
    return values, sources


def _read_yaml_file() -> dict[str, Any]:
    for path in YAML_FILES:
        if not path.is_file():
            continue
        try:
            import yaml      # 可选依赖（wewrite 已依赖 PyYAML）
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}

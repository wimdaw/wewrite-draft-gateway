"""
wewrite-draft-gateway —— 把 WeWrite 的排版结果推送到自建公众号草稿网关。

Python 调用示例::

    from wewrite_gateway import Settings, render_article, push_draft

    st = Settings.load()                                # 读环境变量 / .env / 配置文件
    art = render_article("article.md", theme="sspai")   # 用 wewrite 排版（18 套主题）
    result = push_draft(st, art, cover="cover.png")     # 推到 wx-draft-worker 网关
    print(result["media_id"])

CLI 用法见 ``wewrite-push --help``，完整文档见 README.md。
"""

from .config import ConfigError, Settings
from .gateway import GatewayClient, GatewayError, build_payload, file_to_data_uri, push_draft
from .render import Article, available_themes, render_article, render_html_file

__version__ = "1.0.0"

__all__ = [
    "Settings",
    "ConfigError",
    "Article",
    "render_article",
    "render_html_file",
    "available_themes",
    "GatewayClient",
    "GatewayError",
    "build_payload",
    "file_to_data_uri",
    "push_draft",
    "__version__",
]

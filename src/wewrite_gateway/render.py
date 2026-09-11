"""Markdown → 微信兼容 HTML 的排版层。

复用 WeWrite 的排版内核（18 套主题、内联样式、微信 HTML 白名单清洗），
本模块只负责“拿到干净的正文 HTML”，不碰微信 API。

降级链（保证任何环境下都能工作）：
    1. 直接 import wewrite.toolkit.converter（最快，推荐）
    2. 调用 wewrite CLI 生成预览页，从 <body> 中提取正文
    3. 都没有 → 只返回 Markdown，让网关侧用自带的渲染器排版
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_THEME = "professional-clean"
_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.S | re.I)
_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.M)


@dataclass
class Article:
    """一篇待推送的文章。``html`` 为空时按 Markdown 交给网关渲染。"""

    markdown: str
    html: str = ""
    title: str = ""
    digest: str = ""
    theme: str = DEFAULT_THEME
    source_path: Optional[Path] = None
    images: list[str] = field(default_factory=list)
    renderer: str = "none"   # wewrite-api / wewrite-cli / gateway-markdown

    @property
    def chars(self) -> int:
        return len(self.markdown)


# --------------------------------------------------------------- 主题与工具
def available_themes() -> list[str]:
    """列出 wewrite 自带主题（读 toolkit/themes/*.yaml）。"""
    try:
        import wewrite.toolkit  # noqa: F401
        pkg = Path(sys.modules["wewrite.toolkit"].__file__).parent / "themes"
        return sorted(p.stem for p in pkg.glob("*.yaml"))
    except Exception:
        return []


def wewrite_version() -> Optional[str]:
    try:
        from importlib.metadata import version
        return version("wewrite")
    except Exception:
        return None


def _extract_title(md: str) -> str:
    m = _H1_RE.search(md)
    if m:
        return m.group(1).strip()
    for line in md.splitlines():
        if line.strip():
            return re.sub(r"[#*`>\-]+", "", line).strip()[:64]
    return "未命名文章"


def _extract_body(full_html: str) -> str:
    m = _BODY_RE.search(full_html)
    return m.group(1).strip() if m else full_html


# ------------------------------------------------------------------- 主入口
def render_article(
    path: str | Path,
    theme: Optional[str] = None,
    title: Optional[str] = None,
    digest: Optional[str] = None,
) -> Article:
    """把 Markdown 文件排版成微信正文 HTML。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"文章不存在：{p}")
    md = p.read_text(encoding="utf-8")
    theme = theme or DEFAULT_THEME

    art = Article(markdown=md, title=title or _extract_title(md), digest=digest or "",
                  theme=theme, source_path=p)

    # 1) in-process wewrite
    try:
        from wewrite.toolkit.converter import WeChatConverter

        res = WeChatConverter(theme_name=theme).convert(md)
        art.html = res.html
        art.title = title or art.title or getattr(res, "title", "")
        art.digest = digest or getattr(res, "digest", "") or ""
        art.images = list(getattr(res, "images", []) or [])
        art.renderer = "wewrite-api"
        return art
    except ImportError:
        pass
    except Exception as exc:      # 主题名写错等情况要让人看见，而不是静默降级
        raise RuntimeError(f"wewrite 排版失败（theme={theme}）：{exc}") from exc

    # 2) wewrite CLI
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "preview.html"
            cmd = [sys.executable, "-m", "wewrite", "preview", str(p),
                   "--theme", theme, "--no-open", "--no-paste-safe", "-o", str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if out.is_file():
                art.html = _extract_body(out.read_text(encoding="utf-8"))
                art.renderer = "wewrite-cli"
                return art
            raise RuntimeError((r.stderr or r.stdout or "").strip()[:300])
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # 3) 交给网关渲染
    art.renderer = "gateway-markdown"
    return art


def render_html_file(path: str | Path, title: str = "", digest: str = "") -> Article:
    """已经是排版好的 HTML（含内联样式）时，直接推。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"HTML 不存在：{p}")
    html = p.read_text(encoding="utf-8")
    if "<body" in html.lower():
        html = _extract_body(html)
    return Article(markdown="", html=html, title=title or _extract_title(html) or "未命名文章",
                   digest=digest, renderer="html-file")

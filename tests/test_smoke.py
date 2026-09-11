"""离线冒烟测试：不联网、不推送。

    python -m pytest tests -q
    python tests/test_smoke.py        # 不装 pytest 也能跑
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 避免读到本机真实配置（测试必须离线、可重复）
for key in ("WX_GATEWAY_URL", "WX_GATEWAY_TOKEN", "WX_GATEWAY_PROXY"):
    os.environ.pop(key, None)

from wewrite_gateway import Settings, build_payload, push_draft, render_article  # noqa: E402
from wewrite_gateway.config import ConfigError  # noqa: E402, F401
from wewrite_gateway.gateway import file_to_data_uri  # noqa: E402
from wewrite_gateway.render import _extract_body, _extract_title  # noqa: E402

ARTICLE = ROOT / "examples" / "article.md"
COVER = ROOT / "examples" / "cover.png"
SETTINGS = Settings(url="https://gateway.example.workers.dev", token="wxk_test_0000",
                    default_author="百晓文苑")


def test_extract_helpers():
    assert _extract_title("# 你好\n正文") == "你好"
    assert _extract_title("没有标题\n正文") == "没有标题"
    assert "内容" in _extract_body("<html><body><p>内容</p></body></html>")


def test_render_returns_wechat_html():
    article = render_article(ARTICLE, theme="sspai")
    assert article.renderer in {"wewrite-api", "wewrite-cli"}, article.renderer
    assert "<p" in article.html and "style=" in article.html     # 必须是内联样式
    assert article.title                                           # H1 被提取
    assert article.chars > 200


def test_render_unknown_theme_raises():
    try:
        render_article(ARTICLE, theme="不存在的主题")
    except RuntimeError as exc:
        assert "排版失败" in str(exc)
    else:                                                          # pragma: no cover
        raise AssertionError("未知主题应当报错，而不是静默降级")


def test_payload_field_names_match_gateway():
    article = render_article(ARTICLE, theme="professional-clean")
    payload = build_payload(article, SETTINGS, cover=str(COVER), account_id="acc-1",
                            source_url="https://example.com/a")
    for key in ("title", "content", "contentType", "author", "digest", "cover",
                "accountId", "contentSourceUrl"):
        assert key in payload, f"缺少字段 {key}"
    assert payload["contentType"] == "html"
    assert payload["cover"].startswith("data:image/png;base64,")
    assert payload["accountId"] == "acc-1"


def test_author_truncated_to_8_chars():
    article = render_article(ARTICLE)
    payload = build_payload(article, SETTINGS, author="一二三四五六七八九十")
    assert payload["author"] == "一二三四五六七八"          # 微信限制


def test_title_truncated_to_64_chars():
    article = render_article(ARTICLE)
    payload = build_payload(article, SETTINGS, title="标" * 80)
    assert len(payload["title"]) == 64


def test_markdown_fallback_content_type():
    class Dummy:
        markdown = "# 标题\n正文"
        html = ""
        title = "标题"
        digest = ""

    payload = build_payload(Dummy(), SETTINGS)
    assert payload["contentType"] == "markdown"            # 无 HTML 时交给网关渲染


def test_file_to_data_uri_rejects_non_image():
    try:
        file_to_data_uri(ROOT / "README.md")
    except Exception as exc:
        assert "封面必须是图片" in str(exc)
    else:                                                   # pragma: no cover
        raise AssertionError("非图片文件应当被拒绝")


def test_dry_run_never_touches_network():
    article = render_article(ARTICLE)
    blank = Settings()                                      # 没有任何配置
    result = push_draft(blank, article, dry_run=True, cover=str(COVER))
    assert result["dry_run"] is True
    assert result["payload"]["title"]


def test_require_reports_missing_config():
    try:
        Settings().require()
    except ConfigError as exc:
        assert "WX_GATEWAY_URL" in str(exc) and "WX_GATEWAY_TOKEN" in str(exc)
    else:                                                   # pragma: no cover
        raise AssertionError("缺配置时必须抛出 ConfigError")


def _run_all():
    tests = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
        except Exception as exc:                            # noqa: BLE001
            failed += 1
            print(f"  ❌ {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())

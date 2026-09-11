"""命令行入口：``wewrite-push``。

    wewrite-push push article.md --cover cover.png --theme sspai --title "标题"
    wewrite-push doctor            # 体检：配置 / 网关 / 令牌 / 排版内核
    wewrite-push themes            # 列出可用的排版主题
    wewrite-push drafts --count 5  # 看草稿箱最近几条（核对推送结果）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, Settings
from .gateway import GatewayClient, GatewayError, build_payload, push_draft
from .render import (Article, available_themes, render_article, render_html_file,
                     wewrite_version)

OK, WARN, BAD = "✅", "⚠️ ", "❌"


def _print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------- push
def cmd_push(args: argparse.Namespace) -> int:
    settings = Settings.load(url=args.url, token=args.token, theme=args.theme,
                             account_id=args.account_id)
    if args.proxy:
        settings.proxy = args.proxy

    article = (render_html_file(args.article, title=args.title or "") if args.html
               else render_article(args.article, theme=settings.default_theme or args.theme,
                                   title=args.title))

    print(f"📄 {args.article}  →  {article.chars} 字 / 排版内核：{article.renderer}"
          + (f" / 主题：{article.theme}" if article.renderer != "html-file" else ""))
    if article.renderer == "gateway-markdown":
        print(f"{WARN}未检测到 wewrite 排版内核，改为把 Markdown 交给网关渲染"
              f"（安装：pip install wewrite）")

    result = push_draft(
        settings, article, dry_run=args.dry_run,
        cover=args.cover, cover_url=args.cover_url, title=args.title, digest=args.digest,
        author=args.author, account_id=args.account_id, source_url=args.source_url,
        open_comment=args.open_comment, only_fans_comment=args.only_fans_comment,
    )

    if args.dry_run:
        payload = dict(result["payload"])
        if len(payload.get("content", "")) > 200:
            payload["content"] = payload["content"][:200] + f"...（共 {article.chars} 字）"
        if payload.get("cover", "").startswith("data:"):
            payload["cover"] = payload["cover"][:40] + f"...（data URI，共 {len(payload['cover'])} 字节）"
        print("🧪 dry-run：以下内容已渲染但未推送\n")
        _print_json(payload)
        return 0

    print(f"{OK}已推送到草稿箱")
    print(f"   media_id : {result.get('media_id')}")
    print(f"   公众号   : {result.get('account') or '（默认账号）'}")
    print(f"   图片转存 : {result.get('images', 0)} 张成功"
          + (f"，{len(result['failed_images'])} 张失败" if result.get("failed_images") else ""))
    print("\n打开微信公众平台 → 草稿箱即可看到并群发/发布。")
    return 0


# ------------------------------------------------------------------- doctor
def cmd_doctor(args: argparse.Namespace) -> int:
    problems = 0
    print(f"wewrite-draft-gateway {__version__}\n" + "-" * 52)

    print(f"{OK}Python {sys.version.split()[0]}")

    ver = wewrite_version()
    if ver:
        print(f"{OK}排版内核 wewrite {ver}")
    else:
        print(f"{WARN}未安装 wewrite（仍可用，Markdown 将由网关渲染）：pip install wewrite")
        problems += 1

    themes = available_themes()
    print(f"{OK}可用主题 {len(themes)} 个" + (f"：{', '.join(themes[:6])}..." if themes else ""))

    settings = Settings.load(url=args.url, token=args.token)
    for label, value, key in (("网关地址", settings.url, "WX_GATEWAY_URL"),
                              ("业务令牌", settings.token, "WX_GATEWAY_TOKEN")):
        if not value:
            print(f"{BAD}{label}未配置（{key}）")
            problems += 1
        else:
            shown = value if label == "网关地址" else (value[:8] + "…" + value[-4:] if len(value) > 14 else "已配置")
            from_where = settings.source.get(key, "未知来源")
            print(f"{OK}{label}：{shown}   ← {from_where}")

    if not settings.url:
        print("\n体检中止：先配置 WX_GATEWAY_URL / WX_GATEWAY_TOKEN。")
        return 1

    client = GatewayClient(settings)
    try:
        health = client.health()
        print(f"{OK}网关健康检查通过：" + json.dumps(health, ensure_ascii=False)[:160])
    except GatewayError as exc:
        print(f"{BAD}网关健康检查失败：{exc}")
        problems += 1

    if settings.token:
        try:
            data = client.drafts(count=1)
            total = data.get("total_count", data.get("totalCount", "?"))
            print(f"{OK}令牌有效（草稿箱现有 {total} 条草稿）")
        except GatewayError as exc:
            print(f"{BAD}令牌校验失败：{exc}")
            problems += 1
    else:
        print(f"{WARN}无令牌，跳过鉴权校验")

    print("-" * 52)
    print("体检结论：" + ("全部通过，可以直接推送 🚀" if problems == 0 else f"发现 {problems} 项待处理"))
    return 0 if problems == 0 else 1


# ------------------------------------------------------------------- others
def cmd_themes(args: argparse.Namespace) -> int:
    themes = available_themes()
    if not themes:
        print("未检测到 wewrite，无法列出主题（pip install wewrite）")
        return 1
    current = Settings.load().default_theme
    for name in themes:
        print(("* " if name == current else "  ") + name)
    return 0


def cmd_drafts(args: argparse.Namespace) -> int:
    settings = Settings.load(url=args.url, token=args.token)
    settings.require()
    data = GatewayClient(settings).drafts(count=args.count)
    items = data.get("item") or data.get("items") or []
    print(f"草稿箱共 {data.get('total_count', len(items))} 条，最近 {len(items)} 条：")
    for it in items:
        news = ((it.get("content") or {}).get("news_item") or [{}])[0]
        print(f"  - {news.get('title') or it.get('title') or '（无标题）'}  ({it.get('media_id')})")
    return 0


# --------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wewrite-push",
        description="把 WeWrite 排版好的公众号文章推送到自建 wx-draft-worker 网关（免 access_token、免 IP 白名单）。",
        epilog="示例：wewrite-push push article.md --cover cover.png --theme sspai",
    )
    p.add_argument("--version", action="version", version=f"wewrite-push {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--url", help="网关地址（覆盖 WX_GATEWAY_URL）")
        sp.add_argument("--token", help="业务令牌（覆盖 WX_GATEWAY_TOKEN）")
        sp.add_argument("--proxy", help="HTTP 代理，如 http://127.0.0.1:10808")

    sp = sub.add_parser("push", help="渲染并推送一篇文章")
    sp.add_argument("article", help="Markdown 文件路径（或 --html 时的 HTML 文件）")
    common(sp)
    sp.add_argument("--html", action="store_true", help="把 article 当作已排版好的 HTML 处理")
    sp.add_argument("--theme", default=None, help=f"排版主题（默认 {Settings().default_theme or 'professional-clean'}）")
    sp.add_argument("--title", help="标题（默认取正文第一个 # 标题）")
    sp.add_argument("--digest", help="摘要（默认自动生成）")
    sp.add_argument("--author", help="作者（微信限制 ≤ 8 字）")
    sp.add_argument("--cover", help="本地封面图片路径（自动转 data URI 上传）")
    sp.add_argument("--cover-url", help="公网封面图片地址（二选一）")
    sp.add_argument("--account-id", help="推送到哪个公众号（默认用后台默认账号）")
    sp.add_argument("--source-url", help="原文链接（显示在文末）")
    sp.add_argument("--open-comment", type=int, choices=[0, 1], help="0=不开启评论，1=开启")
    sp.add_argument("--only-fans-comment", type=int, choices=[0, 1], help="1=仅粉丝可评论")
    sp.add_argument("--dry-run", action="store_true", help="只渲染不推送，打印将发送的请求体")
    sp.set_defaults(func=cmd_push)

    sp = sub.add_parser("doctor", help="体检：配置 / 网关 / 令牌 / 排版内核")
    common(sp)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("themes", help="列出可用排版主题")
    sp.set_defaults(func=cmd_themes)

    sp = sub.add_parser("drafts", help="查看草稿箱最近几条")
    common(sp)
    sp.add_argument("--count", type=int, default=5)
    sp.set_defaults(func=cmd_drafts)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, GatewayError, FileNotFoundError, RuntimeError) as exc:
        print(f"{BAD}{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

# wewrite-draft-gateway

**把 [WeWrite](https://github.com/imraywang/wewrite) 的公众号排版能力，接到自建的 [wx-draft-worker](https://github.com/wimdaw/wx-draft-worker) 草稿网关。**

Markdown 进，公众号草稿箱出 —— 本机不需要公众号 AppSecret，不需要 `access_token`，
不需要把自己的出口 IP 加进白名单。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab.svg)](pyproject.toml)
[![Skill](https://img.shields.io/badge/Claude%20Skill-wewrite--publish-8a63d2.svg)](skills/wewrite-publish/SKILL.md)

```bash
wewrite-push push article.md --theme sspai --cover cover.png --author "百晓文苑"
# ✅ 已推送到草稿箱   media_id : JYYmKckE1u7_3Gyk...   公众号 : 百晓文苑
```

---

## 为什么需要这一层

WeWrite 自带 `wewrite publish`，但它是**直连微信官方接口**的，于是每台写作机器都要面对：

| 麻烦 | 直连微信 | 走本网关 |
|------|----------|----------|
| 凭据 | 每台机器都要有 AppID + AppSecret | 只存网关侧；本机只有一个可随时吊销的 `wxk_` 令牌 |
| `access_token` | 两小时过期，需要自己缓存与刷新 | 网关统一缓存（stable_token） |
| IP 白名单 | 每台机器的出口 IP 都要加白 | 只白名单 Cloudflare 出口段，一处配好 |
| 正文图片 | 逐张上传到微信素材库再替换链接 | 网关自动转存到微信域名 |
| 封面 | 先上传成 `thumb_media_id` | 直接给本地图片或图片 URL，网关处理 |
| 多公众号 | 手工切换凭据 | `--account-id` 一个参数 |

WeWrite 负责**内容与排版**（18 套主题、内联样式、微信 HTML 白名单清洗），网关负责**与微信打交道**，
这一层适配器负责把两者粘起来——并给你一条命令。

## 架构

```
   Markdown 文章
        │
        │  ① 排版（本地，WeWrite 内核，18 套主题）
        ▼
   微信兼容 HTML（内联样式，body 片段）
        │
        │  ② POST /api/draft   X-API-Key: wxk_xxx
        ▼
   wx-draft-worker（Cloudflare Worker）
        │   · 缓存 access_token
        │   · 正文图片 → 微信域名
        │   · 封面 → thumb_media_id
        │   · 提交草稿
        ▼
   公众号草稿箱  →  打开后台点「发布」
```

## 快速开始

### 1. 装

```bash
pip install wewrite-draft-gateway

# 从源码安装（开发用）
git clone https://github.com/wimdaw/wewrite-draft-gateway
cd wewrite-draft-gateway && pip install -e .
```

要求 Python ≥ 3.11（WeWrite 的硬性要求）。排版内核 `wewrite` 会作为依赖一起装上。

### 2. 配

只需要两项。在项目根目录建 `.env`：

```ini
WX_GATEWAY_URL=https://wx-draft-worker.<你的子域>.workers.dev
WX_GATEWAY_TOKEN=wxk_xxxxxxxxxxxxxxxxxxxxxxxx
```

也可以写成环境变量，或用 `--url` / `--token` 临时覆盖。全部键名见 [`.env.example`](.env.example)。

**令牌怎么来**：打开网关后台 → 登录 → 「令牌管理」→ 新建令牌 → 复制 `wxk_` 开头的字符串。
（令牌只在创建时完整显示一次，请立即保存。）

### 3. 体检

```bash
wewrite-push doctor
```

```
wewrite-draft-gateway 1.0.0
----------------------------------------------------
✅Python 3.12.14
✅排版内核 wewrite 4.2.1
✅可用主题 18 个：bauhaus, bold-green, bold-navy, bytedance, elegant-rose, focus-red...
✅网关地址：https://wx-draft-worker.xxx.workers.dev   ← 环境变量 WX_GATEWAY_URL
✅业务令牌：wxk_2d96…cb56   ← 环境变量 WX_GATEWAY_TOKEN
✅网关健康检查通过：{"service": "wx-draft-worker", ...}
✅令牌有效（草稿箱现有 3 条草稿）
----------------------------------------------------
体检结论：全部通过，可以直接推送 🚀
```

### 4. 推

```bash
wewrite-push push examples/article.md --theme sspai --cover examples/cover.png --author "百晓文苑"
```

没有封面图时可以用附带的脚本生成一张：

```bash
python examples/make_cover.py examples/cover.png "文章标题"
```

想先看看会发什么，加 `--dry-run`：只渲染、只打印请求体，不推送。

---

## 四种调用方式

完整细节见 [docs/usage.md](docs/usage.md)，这里给最短可用版本。

### A. 命令行

```bash
wewrite-push push article.md --theme sspai --cover cover.png --author "百晓文苑"
wewrite-push themes                       # 列出 18 套主题
wewrite-push drafts --count 5             # 核对草稿箱
wewrite-push push article.md --dry-run    # 只看请求体，不推送
```

### B. Python

```python
from wewrite_gateway import Settings, render_article, push_draft

st  = Settings.load()
art = render_article("posts/2026-09-11.md", theme="sspai")
res = push_draft(st, art, cover="assets/cover.png", author="百晓文苑")
print(res["media_id"])
```

### C. HTTP / curl / 任意语言

```bash
curl -X POST "$WX_GATEWAY_URL/api/draft" \
  -H "X-API-Key: $WX_GATEWAY_TOKEN" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36" \
  -H "Content-Type: application/json" \
  -d '{"title":"标题","content":"# 正文","contentType":"markdown"}'
```

字段与错误码见 [docs/gateway-api.md](docs/gateway-api.md)。

### D. AI Agent（Claude Code 技能）

```bash
bash scripts/install.sh          # 把网关版技能装到 ~/.claude/skills
```

装上之后，对 Agent 说一句「把这篇推成草稿」就够了。技能（[skills/wewrite-publish/SKILL.md](skills/wewrite-publish/SKILL.md)）
强制它按这个顺序走：`doctor` → 本地预览 → `--dry-run` 给你看 → **你确认后才真正推送** → `drafts` 核对。

## 参数速查

| 参数 | 说明 |
|------|------|
| `--theme <名>` | 排版主题（`wewrite-push themes` 查看，默认 `professional-clean`） |
| `--title` / `--digest` / `--author` | 覆盖标题 / 摘要 / 作者（作者 ≤ 8 字） |
| `--cover <路径>` / `--cover-url <URL>` | 本地封面图（自动转 data URI）/ 公网图片 |
| `--account-id <id>` | 多公众号矩阵时指定目标账号 |
| `--source-url <URL>` | 原文链接（文末「阅读原文」） |
| `--open-comment 0\|1` | 是否开启评论 |
| `--only-fans-comment 0\|1` | 仅粉丝可评论 |
| `--html` | 把输入当已排版好的 HTML |
| `--dry-run` | 只渲染不推送 |
| `--url` / `--token` / `--proxy` | 临时覆盖配置 |

环境变量：`WX_GATEWAY_URL`、`WX_GATEWAY_TOKEN`、`WX_GATEWAY_AUTHOR`、`WX_GATEWAY_THEME`、
`WX_GATEWAY_ACCOUNT_ID`、`WX_GATEWAY_PROXY`、`WX_GATEWAY_UA`、`WX_GATEWAY_TIMEOUT`。

## 与 `wewrite publish` 的差异

| 项目 | `wewrite publish`（原版） | `wewrite-push push`（本版） |
|------|--------------------------|----------------------------|
| 凭据 | AppID + AppSecret | 网关地址 + `wxk_` 令牌 |
| 命令位置 | WeWrite 包内 | 独立的薄适配层 |
| 需要 IP 白名单 | 是（本机出口 IP） | 否（网关侧已配 Cloudflare 段） |
| 需要 wewrite 排版内核 | 是 | **可选**（没装时交给网关用自带渲染器排版） |
| 多公众号 | 手动换凭据 | `--account-id` |

WeWrite 的选题、写作、审稿、配图等其余模块完全不受影响，可以照常使用。

## 排错

| 现象 | 原因与处理 |
|------|-----------|
| `缺少配置：WX_GATEWAY_URL` | 没配 `.env` 或环境变量；`wewrite-push doctor` 会告诉你每个值从哪来 |
| HTTP `401` | 令牌无效/已停用 → 后台「令牌管理」重建 |
| HTTP `403` / 错码 `1010` | Cloudflare Bot 拦截 → 请求需带浏览器 UA（本工具默认已带） |
| `40164` | 出口 IP 不在白名单 → 把 Cloudflare 全部 IPv4 段加入公众号后台 IP 白名单 |
| `40001` / `40013` | AppSecret / AppID 无效 → 后台「公众号管理」重新保存 |
| `53500` | 公众号没有草稿接口权限 → 需已认证公众号 |
| `尚未添加公众号` | 后台没添加 AppID/AppSecret，或未设为默认账号 |
| `无法生成封面` | 没传 `--cover` 且正文里没有图片 |
| 推送成功但后台看不到 | 微信草稿箱有缓存，刷新页面；也可 `wewrite-push drafts --count 5` 交叉验证 |

## 目录结构

```
wewrite-gateway/
├─ src/wewrite_gateway/
│  ├─ cli.py        # wewrite-push 命令（push / doctor / themes / drafts）
│  ├─ config.py     # 配置：参数 > 环境变量 > .env > YAML
│  ├─ render.py     # Markdown → 微信 HTML（WeWrite 内核，含降级链）
│  └─ gateway.py    # 网关 HTTP 客户端 + 请求体组装 + 中文错误解释
├─ skills/wewrite-publish/SKILL.md   # 给 AI Agent 用的技能（覆盖原版发布模块）
├─ docs/
│  ├─ usage.md          # 四种调用方式详解
│  └─ gateway-api.md    # 网关接口字段与错误码
├─ examples/
│  ├─ article.md        # 示例文章
│  └─ make_cover.py     # 用 Pillow 生成纯色封面（无版权风险）
└─ scripts/install.sh   # 安装技能到 Agent 技能目录
```

## 开发与自测

```bash
pip install -e .
python -m pytest tests -q        # 离线冒烟：不联网、不推送
python -m wewrite_gateway doctor # 线上体检
```

`--dry-run` 是做集成测试最安全的姿势：会走完整的渲染路径，但不产生任何副作用。

## 相关项目

- [WeWrite](https://github.com/imraywang/wewrite)：Markdown → 微信 HTML 的排版内核（18 套主题）
- [wx-draft-worker](https://github.com/wimdaw/wx-draft-worker)：Cloudflare Worker 网关，负责 token、图片转存与草稿提交

## 许可

MIT © wimdaw

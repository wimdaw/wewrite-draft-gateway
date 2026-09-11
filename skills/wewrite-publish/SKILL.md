---
name: wewrite-publish
description: |
  WeWrite 排版发布模块（自建网关版）：把 Markdown 排成微信预览，或在用户明确授权后推入公众号草稿箱。
  推送不再直连微信，而是调用自建 wx-draft-worker 网关的 POST /api/draft：
  本机不需要公众号 AppSecret、不需要 access_token、不需要把出口 IP 加白名单。
  只处理微信公众号。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
---

# wewrite-publish — 排版、预览、草稿箱（网关版）

本文件覆盖原版 `wewrite-publish`：**排版与预览仍然用 WeWrite，推送改成走自建网关**。
网关负责 access_token 缓存、正文图片转存微信域名、封面生成、草稿提交，本机只发一个 HTTP 请求。

## 前置

```bash
# 1) 安装（任选其一）
pip install wewrite-draft-gateway          # 已发布到 PyPI 时
pip install -e /path/to/wewrite-gateway    # 从源码安装

# 2) 配置两项，写进项目里的 .env 或环境变量
#    WX_GATEWAY_URL=https://wx-draft-worker.<你的子域>.workers.dev
#    WX_GATEWAY_TOKEN=wxk_xxx      ← 网关后台「令牌管理」创建

# 3) 体检：配置 / 网关 / 令牌 / 排版内核
wewrite-push doctor
```

`doctor` 全绿才继续；任何一项 ❌ 时先修好，不要尝试推送。

## 执行顺序

### 1. 本地预览排版（不推送）

```bash
wewrite preview {article} --theme {theme} --no-open -o preview.html
```

把 `preview.html` 路径告诉用户，说明主题与配图情况。想换主题时列出 `wewrite-push themes`。

### 2. 推送前先给用户看请求体

```bash
wewrite-push push {article} --theme {theme} --cover {cover} --dry-run
```

`--dry-run` 会打印标题、摘要、作者、封面大小，不产生任何副作用。用户确认后再进下一步。

### 3. 用户明确授权后推送

```bash
wewrite-push push {article} \
  --theme {theme} \
  --cover {cover} \
  --title "{title}" \
  --digest "{digest}" \
  --author "{author}"
```

成功输出包含 `media_id` 与目标公众号名；失败会给出中文原因（如 40164 IP 白名单、40001 AppSecret、封面缺失）。

- 多公众号矩阵：加 `--account-id {id}`，不传则用网关后台的默认公众号。
- 已经是排好版的 HTML：`wewrite-push push article.html --html --cover cover.png`。
- 正文自带图片时可以不传 `--cover`，网关会自动取正文第一张图当封面。

### 4. 核对

```bash
wewrite-push drafts --count 3
```

新草稿出现在列表里即为端到端成功。

## 边界与失败处理

- **只在用户明确授权时推送**；预览与 dry-run 不构成发布授权。
- 正文超过 20000 字、图片超过 10 张、表格超过 4 列时，先精简再推（微信限制）。
- 推送失败时保留本地 Markdown 与 `preview.html`，向用户报告网关返回的原始错误与对应处理建议；不要自动重试超过一次。
- 图片转存失败（返回 `failed_images`）时提示：可把图片换成微信可访问的公网地址后重推。
- 令牌失效（HTTP 401）时提示用户到网关后台「令牌管理」重新生成。

## 与原版 `wewrite publish` 的差异

| 项目 | 原版（直连微信） | 本版（走网关） |
|------|------------------|----------------|
| 所需凭据 | AppID + AppSecret | 网关地址 + `wxk_` 令牌 |
| access_token | 本机获取与缓存 | 网关缓存（stable_token） |
| IP 白名单 | 必须把本机出口 IP 加白 | 只白名单 Cloudflare 出口段（已配好） |
| 正文图片 | 本机逐张上传素材 | 网关转存微信域名 |
| 封面 | 本机先上传成 thumb_media_id | 网关接受本地 data URI / 图片 URL，自动处理 |
| 多公众号 | 手动切换凭据 | `--account-id` 一个参数 |
| 命令 | `wewrite publish …` | `wewrite-push push …` |

写作、选题、审稿、配图等其它 WeWrite 模块完全不变。

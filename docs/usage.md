# 四种调用方式

同一个网关接口，选择你最顺手的入口。四种方式互不冲突，输出完全一致。

---

## 方式一：命令行（推荐）

```bash
# 安装
pip install wewrite wewrite-draft-gateway

# 配置（项目根目录 .env）
cat > .env <<'EOF'
WX_GATEWAY_URL=https://wx-draft-worker.<你的子域>.workers.dev
WX_GATEWAY_TOKEN=wxk_xxxxxxxx
EOF

# 体检 → 预览 → 推送
wewrite-push doctor
wewrite-push push article.md --theme sspai --cover cover.png --dry-run
wewrite-push push article.md --theme sspai --cover cover.png --author "百晓文苑"
```

成功输出：

```
📄 article.md  →  1122 字 / 排版内核：wewrite-api / 主题：sspai
✅已推送到草稿箱
   media_id : JYYmKckE1u7_3GykmLNiJCUVAYqBAJYvw3cYxTw1jdcZMTcn5pfMBE72eVIK41tO
   公众号   : 百晓文苑
   图片转存 : 0 张成功
```

### 子命令

| 命令 | 作用 |
|------|------|
| `wewrite-push push <文件>` | 排版并推送（`--html` 时按已排版的 HTML 处理） |
| `wewrite-push doctor` | 体检：Python / wewrite 内核 / 网关连通 / 令牌 / 默认主题 |
| `wewrite-push themes` | 列出 18 套排版主题，`*` 标记当前默认 |
| `wewrite-push drafts --count 5` | 查看草稿箱最近几条（核对是否推送成功） |

### push 的常用参数

| 参数 | 说明 |
|------|------|
| `--theme <名>` | 排版主题，默认 `professional-clean` |
| `--title / --digest / --author` | 覆盖标题 / 摘要 / 作者（作者 ≤ 8 字） |
| `--cover <路径>` | 本地封面图，自动转 data URI 上传 |
| `--cover-url <URL>` | 公网封面图（与 `--cover` 二选一） |
| `--account-id <id>` | 多公众号矩阵时指定目标账号 |
| `--source-url <URL>` | 原文链接（文末「阅读原文」） |
| `--open-comment 0/1` | 是否开启评论 |
| `--only-fans-comment 1` | 仅粉丝可评论 |
| `--dry-run` | 只渲染不推送，打印将发送的 JSON |
| `--url / --token / --proxy` | 临时覆盖配置 |

---

## 方式二：Python 调用（集成进自己的程序）

```python
from wewrite_gateway import Settings, render_article, push_draft

settings = Settings.load()                     # 环境变量 / .env / YAML 自动读取
article = render_article("posts/2026-09-11.md", theme="sspai")

result = push_draft(
    settings,
    article,
    cover="assets/cover.png",                  # 也可用 cover_url="https://..."
    author="百晓文苑",
    account_id=None,                           # 不传则用后台默认公众号
    source_url="https://example.com/original",
)
print(result["media_id"], result["account"])
```

需要自己的会话 / 代理 / 重试策略时，直接用底层客户端：

```python
from wewrite_gateway import GatewayClient, Settings

client = GatewayClient(Settings.load())
print(client.health())                          # 健康检查（不需要令牌）
print(client.drafts(count=5))                   # 草稿列表
client.push({"title": "标题", "content": "<p>HTML</p>", "contentType": "html"})
```

只渲染不推送：

```python
from wewrite_gateway import build_payload, Settings, render_article

payload = build_payload(render_article("a.md", theme="bold-navy"), Settings.load(),
                        cover="cover.png")
print(payload["title"], payload["contentType"], len(payload["content"]))
```

---

## 方式三：HTTP / curl（任意语言）

```bash
curl -X POST "$WX_GATEWAY_URL/api/draft" \
  -H "X-API-Key: $WX_GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36" \
  -d '{"title":"标题","author":"作者","content":"# 正文 Markdown","contentType":"markdown"}'
```

> 注意：`User-Agent` 不能省，Cloudflare 会拦默认的 `curl/8.x`（错误码 `1010`）。
> 也可以让 `wewrite-push push --dry-run` 打印请求体后直接复制粘贴。

字段说明见 [gateway-api.md](gateway-api.md)。

---

## 方式四：AI Agent（Claude Code / 其它 Agent）

把 `skills/wewrite-publish/` 覆盖到 Agent 的技能目录：

```bash
bash scripts/install.sh                     # 默认 ~/.claude/skills
```

之后 Agent 的发布动作变成：

1. `wewrite-push doctor` —— 先体检；
2. `wewrite preview article.md --theme sspai -o preview.html` —— 给用户看排版；
3. `wewrite-push push article.md --cover cover.png --dry-run` —— 给用户看请求体；
4. 用户确认后 `wewrite-push push article.md --cover cover.png` —— 真正推送；
5. `wewrite-push drafts --count 3` —— 核对。

技能文件里已写明「只在用户明确授权时推送」「失败不要自动重试超过一次」等边界。

---

## 配置优先级

命令行参数 > 环境变量 > 当前目录 `.env` / `.env.local` > `~/.wewrite-gateway.env`
> `~/.config/wewrite-gateway.yaml` > 内置默认值。

所有键名与含义见仓库根目录的 `.env.example`。
`wewrite-push doctor` 会打印每个值的**来源**，排查配置问题最省事。

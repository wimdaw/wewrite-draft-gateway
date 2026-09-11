# 网关接口速查（wx-draft-worker）

本适配器只用到三个接口。完整文档见网关仓库的 `API.md`
（示例部署：`https://wx-draft-worker.<你的子域>.workers.dev`）。

## 鉴权

| 方式 | 写法 |
|------|------|
| 请求头（推荐） | `X-API-Key: wxk_xxxxxxxx` |
| 查询参数 | `?key=wxk_xxxxxxxx` |
| Bearer | `Authorization: Bearer wxk_xxxxxxxx` |

令牌在网关后台「令牌管理」创建；网关未配置任何令牌时才允许匿名（开放模式）。
另外要注意：**Cloudflare 会拦非浏览器 UA**，所以请求务必带上正常的 `User-Agent`
（本适配器默认已带 Chrome UA，被拦时返回 `1010`）。

## 1. 新建草稿（核心）

```
POST /api/draft
Content-Type: application/json
X-API-Key: wxk_xxx
```

请求体字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 标题，缺省「未命名文章」，超 64 字截断 |
| `author` | string | 作者，微信限制 ≤ 8 字 |
| `digest` | string | 摘要，缺省由正文自动生成（≤ 120 字） |
| `content` | string | **必填**，正文 |
| `cover` | string | 封面：远程图片 URL 或 `data:image/png;base64,...`；缺省取正文第一张图 |
| `contentType` | `html` \| `markdown` | 缺省自动识别（不含 HTML 标签即按 Markdown 渲染） |
| `contentSourceUrl` | string | 原文链接，显示为「阅读原文」 |
| `needOpenComment` | `0` \| `1` | 0 = 不开启评论，其它值开启（默认开启） |
| `onlyFansCanComment` | `0` \| `1` | 1 = 仅粉丝可评论 |
| `accountId` | string | 目标公众号 id，缺省用后台默认公众号 |

成功响应：

```json
{
  "ok": true,
  "data": {
    "media_id": "JYYmKckE1u7_...",
    "title": "文章标题",
    "images": 0,
    "failed_images": [],
    "account": "百晓文苑"
  }
}
```

失败响应：`{"ok": false, "error": "..."}`，HTTP 状态码 4xx/5xx。

## 2. 草稿列表

```
GET /api/drafts?count=5
```

条目结构：`data.item[].content.news_item[0].title` 为标题，`data.item[].media_id` 为 id。

## 3. 健康检查

```
GET /api/health          # 无需鉴权
```

返回 `service / version / appid_configured / secret_configured / auth_enabled / db_connected`。

## 常见错误码对照

| 现象 | 原因与处理 |
|------|-----------|
| `401` | 令牌无效或已停用 → 后台「令牌管理」重建 |
| `1010`（403） | Cloudflare Bot 拦截 → 请求带浏览器 UA |
| `40164` | 出口 IP 不在白名单 → 把 Cloudflare 全部 IPv4 段加入公众号后台 IP 白名单 |
| `40001` / `40013` | AppSecret / AppID 无效 → 后台「公众号管理」重新保存 |
| `45009` | 微信接口调用超限 → 稍后重试（网关已缓存 token） |
| `53500` | 公众号无草稿权限 → 需已认证公众号 |
| `尚未添加公众号` | 后台没添加 AppID/AppSecret，或未设为默认 |
| `无法生成封面` | 没传 `cover` 且正文无图片 |

## curl 等价写法

```bash
curl -X POST "$WX_GATEWAY_URL/api/draft" \
  -H "X-API-Key: $WX_GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36" \
  -d '{
    "title": "标题",
    "author": "作者",
    "content": "<p>正文 HTML</p>",
    "contentType": "html",
    "cover": "https://example.com/cover.png",
    "accountId": "可选"
  }'
```

`wewrite-push --dry-run` 打印的请求体可以直接喂给这个 curl。

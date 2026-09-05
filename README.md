# 🎬 视频去水印解析服务 (video-watermark-remover)

| 项目 | 地址 |
|------|------|
| **在线页面** | [https://aolined.github.io/video-watermark-remover/](https://aolined.github.io/video-watermark-remover/) |
| **仓库** | [https://github.com/Aolined/video-watermark-remover](https://github.com/Aolined/video-watermark-remover) |
| **本地目录** | `D:\文档\ChatGPT\My 网站\video-watermark-remover` |

> 基于 [parse-video-py](https://github.com/wujunwei928/parse-video-py)（MIT License）二次开发。

支持 **27 个平台** 短视频/图集去水印解析：抖音、快手、B站、小红书、微博、西瓜视频、
微视、最右、虎牙、AcFun、腾讯视频、搜狐、央视网、皮皮虾、梨视频、好看视频、
度小视、全民K歌、TikTok、Instagram 等。

---

## 🏗 架构

```
┌─────────────────────┐        ┌──────────────────────────┐
│  在线页面 (GitHub Pages)  │  HTTP │  后端解析 API (FastAPI)      │
│  docs/index.html      │ ─────▶ │  27 平台去水印解析器            │
│  纯静态，可配置 API 地址    │        │  /video/share/url/parse/batch│
└─────────────────────┘        └──────────────────────────┘
   https://aolined.github.io/     本地: 127.0.0.1:8000
   video-watermark-remover/       云端: Render / VPS
```

去水印解析逻辑必须运行在后端（各平台接口有反爬与签名校验），GitHub Pages 仅托管前端页面。
**在线页面通过"API 地址"设置连接到你的后端服务。**

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🆕 **TikTok 解析** | 国际版 TikTok，支持短链接自动展开 |
| 🆕 **Instagram 解析** | Reels / 帖文视频，embed 页面提取直链 |
| 🆕 **批量解析 API** | `POST /video/share/url/parse/batch`，一次解析多链接或整段分享文本 |
| 🆕 **代理下载端点** | `GET /video/download/direct`，后端转发下载，解决跨域/Referer 防盗链（域名白名单 + 内网拦截） |
| 🆕 **平台列表 API** | `GET /platforms` 返回支持的全部平台与域名 |
| 🆕 **现代化 Web UI** | 深色主题、平台徽章、批量解析、视频预览、图集下载 |
| 🆕 **配置化** | `.env` 支持代理、超时、Basic Auth |
| 🆕 **在线静态页面** | `docs/index.html`，GitHub Pages 托管，可配置任意后端 API |
| 🆕 **Windows 一键启动** | `start.bat` 自动建 venv + 装依赖 + 启动 |

---

## 🚀 使用方式

### 方式一：在线页面（需要后端）

1. **本地后端**（本机运行）：
   ```bat
   start.bat
   ```
   然后打开在线页面，把 API 地址设为 `http://127.0.0.1:8000`（本地直连可用）
   或公网映射（ngrok / cpolar）后的地址。

2. **云端后端**（公网可用，推荐）：
   - 打开 [dashboard.render.com](https://dashboard.render.com) → New → Blueprint
   - 选择本仓库，Render 自动读取 `render.yaml` 部署
   - 部署完成后复制公网地址填入在线页面 API 设置即可，无需再开本机。

### 方式二：纯本地

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[all]"
python main.py                    # 打开 http://127.0.0.1:8000
```

### CLI
```bash
parse-video-py parse "https://v.douyin.com/xxx"
parse-video-py parse "https://v.douyin.com/xxx" --format json
```

---

## 🔌 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 界面（后端自带） |
| GET | `/video/share/url/parse?url=...` | 单条链接解析 |
| POST | `/video/share/url/parse/batch` | 批量解析，`{"urls":[...]}` 或 `{"text":"分享文本"}` |
| GET | `/video/id/parse?source=douyin&video_id=...` | 按平台+ID 解析 |
| GET | `/video/download/direct?url=...&referer=...` | 代理下载（解决防盗链） |
| GET | `/platforms` | 支持平台列表 |
| GET | `/health` | 健康检查 |
| POST | `/mcp` | MCP 接入（StreamableHttp） |

### 批量解析示例
```bash
curl -X POST http://127.0.0.1:8000/video/share/url/parse/batch \
  -H "Content-Type: application/json" \
  -d '{"text":"8.88 复制打开抖音 https://v.douyin.com/xxxx/ 看看这个视频"}'
```

---

## ⚙️ 配置（.env 或环境变量）

| 变量 | 说明 |
|------|------|
| `PARSE_VIDEO_USERNAME` / `PARSE_VIDEO_PASSWORD` | 开启 Basic Auth |
| `PARSE_VIDEO_PROXY` | 代理地址（访问被墙平台时使用） |
| `PARSE_VIDEO_TIMEOUT` | 请求超时秒数，默认 30 |
| `PARSE_VIDEO_RATE_LIMIT` | 每 IP 每分钟请求上限，默认 120；设为 0 关闭限流 |
| `PARSE_VIDEO_BATCH_CONCURRENCY` | 批量解析并发数，默认 5 |
| `PARSE_VIDEO_DOWNLOAD_ALLOW_HOSTS` | 下载白名单追加域名后缀（逗号分隔，不带前导点） |
| `PARSE_VIDEO_DOWNLOAD_ALLOW_ALL` | 设为 `1` 跳过下载域名白名单（内网拦截仍生效），仅自托管排查用 |

### 安全机制
- **CORS**：API 默认允许任意来源跨域调用（在线页面托管于 GitHub Pages，前端不携带凭据），在线页面可直接连接你的云端 API。
- **下载代理防护**：`/video/download/direct` 默认只放行各平台官网与媒体 CDN 域名，解析目标 IP 并拦截内网/回环/保留地址，重定向每一跳都会重新校验，防止被当作开放代理或 SSRF 跳板。
- **限流**：按客户端 IP 滑动窗口限流，默认 120 次/分钟（`/health` 与 CORS 预检不计数）。

---

## 📦 部署

### Render（免费，推荐）
仓库根目录已含 `render.yaml`，Render 一键 Blueprint 部署。

### Docker
```bash
docker build -t video-watermark-remover .
docker run -p 8000:8000 video-watermark-remover
```

---

## ⚠️ 说明
- 解析原理：模拟请求平台公开分享接口/页面，提取无水印媒体直链。
- 部分平台接口可能随版本调整失效，失效时请提供分享链接到 issue。
- 仅用于学习与个人合法用途，请遵守各平台服务条款。

## License
MIT（继承上游 parse-video-py）

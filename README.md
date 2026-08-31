# 视频去水印解析服务 (video-watermark-remover)

> 基于 [parse-video-py](https://github.com/wujunwei928/parse-video-py)（MIT License）二次开发，
> 借鉴 [video_spider](https://github.com/5ime/video_spider) 的多平台思路。

支持 **30+ 平台** 短视频/图集解析去水印：抖音、快手、B站、小红书、微博、西瓜视频、
微视、最右、虎牙、AcFun、腾讯视频、搜狐、央视网、皮皮虾、梨视频、好看视频、
度小视、全民K歌、TikTok、Instagram 等。

---

## ✨ 二改新增功能

| 功能 | 说明 |
|------|------|
| 🆕 **TikTok 解析** | 国际版 TikTok，支持短链接自动展开 |
| 🆕 **Instagram 解析** | Reels / 帖文视频，embed 页面提取直链 |
| 🆕 **批量解析 API** | `POST /video/share/url/parse/batch`，一次解析多链接或整段分享文本 |
| 🆕 **代理下载端点** | `GET /video/download/direct`，后端转发下载，解决跨域/Referer 防盗链 |
| 🆕 **平台列表 API** | `GET /platforms` 返回支持的全部平台与域名 |
| 🆕 **现代化 Web UI** | 深色主题、平台徽章、批量解析、视频预览、图集打包 |
| 🆕 **配置化** | `.env` 支持代理、超时、Basic Auth（`PARSE_VIDEO_PROXY` / `PARSE_VIDEO_TIMEOUT`） |
| 🆕 **Windows 一键启动** | `start.bat` 自动建 venv + 装依赖 + 启动 |

---

## 🚀 快速开始

### Windows
```bat
start.bat
```
访问 http://127.0.0.1:8000

### 手动
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[all]"
python main.py                    # http://127.0.0.1:8000
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
| GET | `/` | Web 界面 |
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

响应：
```json
{"code":200,"msg":"ok","data":{"total":1,"success":1,"failed":0,"results":[{"raw":"https://v.douyin.com/xxxx/","ok":true,"data":{"video_url":"...","title":"...","author":{"name":"..."}}}]}}
```

---

## ⚙️ 配置（.env 或环境变量）

| 变量 | 说明 |
|------|------|
| `PARSE_VIDEO_USERNAME` / `PARSE_VIDEO_PASSWORD` | 开启 Basic Auth |
| `PARSE_VIDEO_PROXY` | 代理地址（访问被墙平台时使用） |
| `PARSE_VIDEO_TIMEOUT` | 请求超时秒数，默认 30 |

复制 `.env.example` 为 `.env` 并按需修改（Web 服务读取环境变量）。

---

## 📦 Docker
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

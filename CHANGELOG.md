# Changelog

所有重要变更均会记录在此文件中。

## [Unreleased]

### 安全加固

- **新增 CORS 支持**：API 允许跨域调用，修复在线页面连接云端后端时被浏览器拦截的问题
- **下载代理 SSRF/开放代理防护**：`/video/download/direct` 默认仅放行各平台官网与媒体 CDN 域名白名单，解析并拦截内网/回环/保留 IP，重定向逐跳重新校验
- **新增按 IP 限流**：滑动窗口默认 120 次/分钟，可通过 `PARSE_VIDEO_RATE_LIMIT` 调整或置 0 关闭

### 优化改进

- **批量解析并发化**：`/video/share/url/parse/batch` 默认并发 5 条且保持结果顺序，可用 `PARSE_VIDEO_BATCH_CONCURRENCY` 调整
- **版本号统一**：FastAPI 服务版本与包版本一致（0.0.3）

---

## [v0.0.3] - 2026-04-19

### 新增功能

- **新增 CLI 命令行工具**：支持 `version`/`parse`/`serve` 三个子命令，可通过 `parse-video-py` 入口直接使用
- **新增 CLI `-h` 简写**：所有命令支持 `-h` 作为 `--help` 的简写
- **新增 pyproject.toml**：使用 hatchling 构建，支持 `[web]`/`[cli]`/`[dev]` 可选依赖安装
- **新增包公开 API**：支持 `from parse_video_py import VideoSource, parse_video_share_url` 直接调用

### 架构重构

- **迁移到 src 标准布局**：`parser/`、`utils/`、`templates/` 统一迁移到 `src/parse_video_py/` 下
- **uv 包管理**：从 venv + requirements.txt 迁移到 uv + pyproject.toml，支持 `uv pip install -e ".[all]"`
- **Web 服务拆分**：从 `main.py` 提取到 `src/parse_video_py/web.py`，`main.py` 改为薄入口
- **URL 工具统一**：`URL_REG` 正则和 `extract_url` 提取到 `utils.py`，消除 web/cli 模块间的重复定义

### 优化改进

- **Web 序列化**：使用 `dataclasses.asdict()` 替代 `__dict__`，正确处理嵌套 dataclass 序列化
- **Auth 依赖缓存**：Basic Auth 依赖在模块加载时构建一次，避免每个路由重复调用
- **批量解析并发限制**：CLI 批量解析添加 `Semaphore(10)` 防止无界并发
- **Dockerfile 更新**：使用 uv 安装依赖，适配 src 布局
- **CI 更新**：GitHub Actions 改用 `astral-sh/setup-uv`

---

## [v0.0.2] - 2026-04-18

### 新增功能

- **新增 B站(哔哩哔哩) 视频解析**：支持 bilibili.com、b23.tv、m.bilibili.com 域名
- **新增 Twitter/X 视频解析**：支持 twitter.com、x.com、t.co 域名
- **新增微博图集解析**：支持微博图片帖子的图集批量提取
- **新增抖音 Live Photo 实况照片支持**：通过 slidesinfo API 提取实况照片视频
- **新增图集批量下载功能**：前端支持图集图片批量下载 (#58)
- **新增 MCP 支持**：通过 StreamableHttp 方式接入 MCP 协议，接入 URL: `/mcp`
- **新增主题样式选择**：前端页面支持多种主题风格切换
- **新增 Basic Auth 自定义认证**：支持通过环境变量自定义用户名密码 (#48)
- **新增 Claude Code 集成**：添加 CLAUDE.md 项目指引和 GitHub Actions CI 工作流

### 优化改进

- **小红书图集图片高清化**：图集图片使用高清地址，优化图片域名替换逻辑 (#45)
- **抖音图集解析音频**：支持抖音图集内容的音频提取 (#70)
- **单元测试覆盖**：添加核心模块单元测试，pre-commit 支持提交时自动运行测试
- **分享链接正则优化**：优化 URL 匹配正则表达式，增强无效输入处理鲁棒性 (#74)
- **依赖管理优化**：整理 requirements.txt 依赖项

### Bug 修复

- **修复无效分享链接导致崩溃**：无效 URL 输入不再导致服务异常
- **修复小红书图片域名替换逻辑**：当图片 URL 不包含 notes_pre_post 时使用原域名

---

## [v0.0.1] - 初始版本

### 基础功能

- 支持 20+ 平台视频去水印解析
- 支持 4 平台图集解析（抖音、快手、小红书、皮皮虾）
- 支持 LivePhoto 解析（小红书）
- FastAPI Web 服务 + REST API 接口
- 前端解析页面
- Docker 部署支持

import asyncio
import dataclasses
import os
import secrets
from pathlib import Path
from urllib.parse import urljoin

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi_mcp import FastApiMCP
from starlette.middleware.base import BaseHTTPMiddleware

from parse_video_py import VideoSource, parse_video_id, parse_video_share_url
from parse_video_py.parser import video_source_info_mapping
from parse_video_py.security import RateLimiter, validate_proxy_url
from parse_video_py.utils import create_async_client, extract_all_urls, extract_url

#: 下载代理最多跟随的重定向跳数
_MAX_REDIRECTS = 5


def _env_int(name: str, default: int) -> int:
    """读取环境变量为整数，非法值时回退默认值。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按客户端 IP 滑动窗口限流；健康检查与 CORS 预检请求不计数。"""

    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next):
        if (
            self.limiter.limit <= 0
            or request.method == "OPTIONS"
            or request.url.path == "/health"
        ):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip() or client_ip
        if not self.limiter.allow(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"code": 429, "msg": "请求过于频繁，请稍后再试"},
            )
        return await call_next(request)


def _get_templates_dir() -> str:
    templates_dir = Path(__file__).parent / "templates"
    if templates_dir.is_dir():
        return str(templates_dir)
    raise FileNotFoundError("templates 目录未找到")


app = FastAPI(title="视频去水印服务", version="0.0.3")

# CORS：在线页面可托管在任意站点（GitHub Pages 等），跨域调用 API 需要放行。
# 前端不携带凭据，保持 allow_credentials=False，因此 allow_origins=["*"] 安全。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# 按 IP 限流，默认 120 次/分钟；PARSE_VIDEO_RATE_LIMIT=0 关闭
app.add_middleware(
    RateLimitMiddleware,
    limiter=RateLimiter(_env_int("PARSE_VIDEO_RATE_LIMIT", 120), 60.0),
)

mcp = FastApiMCP(app)
mcp.mount_http()

templates = Jinja2Templates(directory=_get_templates_dir())


def _build_auth_dependency() -> list[Depends]:
    """根据环境变量动态构建 Basic Auth 依赖项"""
    basic_auth_username = os.getenv("PARSE_VIDEO_USERNAME")
    basic_auth_password = os.getenv("PARSE_VIDEO_PASSWORD")

    if not (basic_auth_username and basic_auth_password):
        return []

    security = HTTPBasic()

    def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
        correct_username = secrets.compare_digest(
            credentials.username, basic_auth_username
        )
        correct_password = secrets.compare_digest(
            credentials.password, basic_auth_password
        )
        if not (correct_username and correct_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials

    return [Depends(verify_credentials)]


_auth_dependency = _build_auth_dependency()


def _ok(data) -> dict:
    return {"code": 200, "msg": "ok", "data": data}


def _fail(code: int, msg: str) -> dict:
    return {"code": code, "msg": msg}


@app.get("/", response_class=HTMLResponse, dependencies=_auth_dependency)
async def read_item(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "视频去水印解析",
        },
    )


@app.get("/video/share/url/parse", dependencies=_auth_dependency)
async def share_url_parse(url: str):
    """解析单条分享链接"""
    video_share_url = extract_url(url)
    if video_share_url is None:
        return _fail(400, "未检测到有效的分享链接")

    try:
        video_info = await parse_video_share_url(video_share_url)
        return _ok(dataclasses.asdict(video_info))
    except Exception as err:
        return _fail(500, str(err))


async def _parse_one(raw: str) -> dict:
    """解析单条链接并返回统一的结果结构。"""
    item = {"raw": raw, "ok": False, "msg": "", "data": None}
    extracted = extract_url(raw)
    if not extracted:
        item["msg"] = "未检测到有效链接"
        return item
    try:
        info = await parse_video_share_url(extracted)
        item["ok"] = True
        item["data"] = dataclasses.asdict(info)
    except Exception as err:
        item["msg"] = str(err)
    return item


@app.post("/video/share/url/parse/batch", dependencies=_auth_dependency)
async def share_url_parse_batch(request: Request):
    """批量解析：请求体为 JSON {"urls": ["...", ...]} 或 {"text": "整段分享文本"}"""
    try:
        payload = await request.json()
    except Exception:
        return _fail(400, "请求体必须为 JSON")

    raw_urls: list[str] = []

    if payload.get("urls"):
        raw_urls = payload["urls"]
    elif payload.get("text"):
        raw_urls = extract_all_urls(payload["text"])
    else:
        return _fail(400, '缺少 "urls" 或 "text" 字段')

    if not raw_urls:
        return _fail(400, "未检测到任何链接")

    # 并发解析但保持结果顺序；默认最多 5 个并发（PARSE_VIDEO_BATCH_CONCURRENCY）
    semaphore = asyncio.Semaphore(max(1, _env_int("PARSE_VIDEO_BATCH_CONCURRENCY", 5)))

    async def _bounded_parse(raw: str) -> dict:
        async with semaphore:
            return await _parse_one(raw)

    results = await asyncio.gather(*(_bounded_parse(raw) for raw in raw_urls))

    ok_count = sum(1 for r in results if r["ok"])
    return _ok(
        {
            "total": len(results),
            "success": ok_count,
            "failed": len(results) - ok_count,
            "results": results,
        }
    )


@app.get("/video/id/parse", dependencies=_auth_dependency)
async def video_id_parse(source: VideoSource, video_id: str):
    """按平台 + 视频ID 解析"""
    try:
        video_info = await parse_video_id(source, video_id)
        return _ok(dataclasses.asdict(video_info))
    except Exception as err:
        return _fail(500, str(err))


@app.get("/platforms", dependencies=_auth_dependency)
async def platforms():
    """返回支持的所有平台列表"""
    items = []
    for src, info in video_source_info_mapping.items():
        items.append(
            {
                "source": src.value,
                "domains": info["domain_list"],
                "parser": info["parser"].__name__,
            }
        )
    return _ok(items)


@app.get("/video/download/direct", dependencies=_auth_dependency)
async def video_download_direct(url: str, referer: str = ""):
    """直接透传下载（与 /video/download 相同，返回原始字节流）。

    安全限制：仅允许白名单内的公网域名，重定向的每一跳都会重新校验，
    避免被当作开放代理或用于访问内网地址（SSRF）。
    """
    validation_error = validate_proxy_url(url)
    if validation_error:
        return _fail(400, validation_error)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    if referer:
        headers["Referer"] = referer

    async def _stream():
        try:
            async with create_async_client(follow_redirects=False) as client:
                current_url = url
                for _hop in range(_MAX_REDIRECTS + 1):
                    hop_error = validate_proxy_url(current_url)
                    if hop_error:
                        yield f'{{"error": "{hop_error}"}}'.encode()
                        return
                    async with client.stream(
                        "GET", current_url, headers=headers
                    ) as resp:
                        if resp.is_redirect:
                            location = resp.headers.get("location")
                            if not location:
                                yield '{"error": "重定向缺少目标地址"}'.encode()
                                return
                            current_url = urljoin(current_url, location)
                            continue
                        resp.raise_for_status()
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            yield chunk
                        return
                yield '{"error": "重定向次数过多"}'.encode()
        except Exception as err:
            yield f'{{"error": "{str(err)}"}}'.encode()

    return StreamingResponse(
        _stream(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="download.bin"',
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/health", dependencies=_auth_dependency)
async def health():
    return _ok({"status": "ok"})


mcp.setup_server()

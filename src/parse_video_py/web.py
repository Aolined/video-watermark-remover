import dataclasses
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi_mcp import FastApiMCP

from parse_video_py import VideoSource, parse_video_id, parse_video_share_url
from parse_video_py.parser import video_source_info_mapping
from parse_video_py.utils import create_async_client, extract_all_urls, extract_url


def _get_templates_dir() -> str:
    templates_dir = Path(__file__).parent / "templates"
    if templates_dir.is_dir():
        return str(templates_dir)
    raise FileNotFoundError("templates 目录未找到")


app = FastAPI(title="视频去水印服务", version="2.0.0")

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

    results = []
    for raw in raw_urls:
        item = {"raw": raw, "ok": False, "msg": "", "data": None}
        extracted = extract_url(raw)
        if not extracted:
            item["msg"] = "未检测到有效链接"
            results.append(item)
            continue
        try:
            info = await parse_video_share_url(extracted)
            item["ok"] = True
            item["data"] = dataclasses.asdict(info)
        except Exception as err:
            item["msg"] = str(err)
        results.append(item)

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
    """直接透传下载（与 /video/download 相同，返回原始字节流）"""
    if not url.startswith("http"):
        return _fail(400, "无效的下载链接")

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
            async with create_async_client(follow_redirects=True) as client:
                async with client.stream("GET", url, headers=headers) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        yield chunk
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



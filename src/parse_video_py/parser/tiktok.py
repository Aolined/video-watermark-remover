import json
import re
from urllib.parse import urlparse

from ..utils import create_async_client
from .base import BaseParser, VideoAuthor, VideoInfo


class TikTok(BaseParser):
    """TikTok 国际版"""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def get_default_headers(self) -> dict:
        return {
            "User-Agent": self.USER_AGENT,
            "Referer": "https://www.tiktok.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def parse_share_url(self, share_url: str) -> VideoInfo:
        # 处理短链接 vt.tiktok.com / vm.tiktok.com
        if "vt.tiktok.com" in share_url or "vm.tiktok.com" in share_url:
            async with create_async_client(follow_redirects=True) as client:
                resp = await client.get(share_url, headers=self.get_default_headers())
                share_url = str(resp.url)

        video_id = self._extract_video_id(share_url)
        if not video_id:
            raise ValueError("无法从链接中解析 TikTok 视频 ID")
        return await self.parse_video_id(video_id)

    async def parse_video_id(self, video_id: str) -> VideoInfo:
        detail_url = f"https://www.tiktok.com/@unknown/video/{video_id}"
        async with create_async_client(follow_redirects=True) as client:
            resp = await client.get(detail_url, headers=self.get_default_headers())
            resp.raise_for_status()
            html = resp.text

        data = self._extract_rehydration_data(html)
        if not data:
            raise ValueError("页面中未找到 TikTok 视频数据 (__UNIVERSAL_DATA_FOR_REHYDRATION__)")

        item_struct = (
            data.get("__DEFAULT_SCOPE__", {})
            .get("webapp.video-detail", {})
            .get("itemInfo", {})
            .get("itemStruct", {})
        )
        if not item_struct:
            # 兜底：SIGI_STATE 结构
            item_struct = (
                data.get("__DEFAULT_SCOPE__", {})
                .get("SIGI_STATE", {})
                .get("ItemModule", {})
                .get(video_id, {})
            )
        if not item_struct:
            raise ValueError("未能从页面数据中提取视频信息")

        video = item_struct.get("video", {}) or {}
        # playAddr 优先，其次 downloadAddr
        play_addr = video.get("playAddr") or video.get("downloadAddr") or {}
        url_list = play_addr.get("urlList") or []

        video_url = ""
        for u in url_list:
            if "watermark" not in u and "playwm" not in u:
                video_url = u
                break
        if not video_url and url_list:
            video_url = url_list[0]
        if not video_url:
            raise ValueError("未找到无水印视频地址")

        author = item_struct.get("author", {}) or {}
        return VideoInfo(
            video_url=video_url,
            cover_url=(item_struct.get("video", {}) or {}).get("cover", "") or "",
            title=(item_struct.get("desc", "") or "").strip()[:200],
            music_url=((item_struct.get("music", {}) or {}).get("playUrl", "") or ""),
            author=VideoAuthor(
                uid=str(author.get("uniqueId", "")),
                name=author.get("nickname", ""),
                avatar=(author.get("avatarLarger", "") or ""),
            ),
        )

    @staticmethod
    def _extract_video_id(share_url: str) -> str:
        parsed = urlparse(share_url)
        parts = [p for p in parsed.path.split("/") if p]
        # 期望路径形如 /@user/video/<id> 或 /video/<id>
        if "video" in parts:
            idx = parts.index("video")
            if idx + 1 < len(parts):
                m = re.match(r"(\d+)", parts[idx + 1])
                if m:
                    return m.group(1)
        return ""

    @staticmethod
    def _extract_rehydration_data(html: str) -> dict:
        pattern = re.compile(
            r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
            re.DOTALL,
        )
        m = pattern.search(html)
        if not m:
            return {}
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return {}

import json
import re
from urllib.parse import urlparse

from ..utils import create_async_client
from .base import BaseParser, VideoAuthor, VideoInfo


class Instagram(BaseParser):
    """Instagram Reels / 帖文视频"""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def get_default_headers(self) -> dict:
        return {
            "User-Agent": self.USER_AGENT,
            "Referer": "https://www.instagram.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def parse_share_url(self, share_url: str) -> VideoInfo:
        shortcode = self._extract_shortcode(share_url)
        if not shortcode:
            raise ValueError("无法从链接中解析 Instagram 短码 (shortcode)")
        return await self.parse_video_id(shortcode)

    async def parse_video_id(self, video_id: str) -> VideoInfo:
        # 方案1：通过 embed 页面获取无签名视频直链
        embed_url = f"https://www.instagram.com/p/{video_id}/embed/captioned/"
        async with create_async_client(follow_redirects=True) as client:
            resp = await client.get(embed_url, headers=self.get_default_headers())
            resp.raise_for_status()
            html = resp.text

        # 提取 <video> 标签中的 src
        video_src = ""
        m = re.search(r'<video[^>]+src="([^"]+)"', html)
        if m:
            video_src = m.group(1)

        # 提取标题
        title = ""
        tm = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if tm:
            title = tm.group(1)

        if not video_src:
            # 方案2：解析 __additionalDataLoaded 中的 graphql 数据
            data = self._extract_additional_data(html)
            if data:
                media = data.get("graphql", {}).get("shortcode_media", {})
                video_src = media.get("video_url", "")
                if not title:
                    title = media.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")[:200]

        if not video_src:
            raise ValueError("未找到 Instagram 视频地址")

        return VideoInfo(
            video_url=video_src,
            cover_url="",
            title=(title or "").strip()[:200],
            author=VideoAuthor(),
        )

    @staticmethod
    def _extract_shortcode(share_url: str) -> str:
        parsed = urlparse(share_url)
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            return ""
        if parts[0] in ("p", "reel", "reels", "tv", "share"):
            return parts[1] if len(parts) > 1 else ""
        # 支持 instagram.com/xxx 形式（旧短码帖）
        return parts[0]

    @staticmethod
    def _extract_additional_data(html: str) -> dict:
        # 匹配 window.__additionalDataLoaded('extra', {...})
        pattern = re.compile(
            r"window\.__additionalDataLoaded\(\s*'extra'\s*,\s*(\{.*?\})\);",
            re.DOTALL,
        )
        m = pattern.search(html)
        if not m:
            return {}
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return {}

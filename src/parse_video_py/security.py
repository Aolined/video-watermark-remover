"""安全相关工具：下载代理的目标校验与接口限流。

- ``validate_proxy_url``：``/video/download/direct`` 的 SSRF 与开放代理防护
- ``RateLimiter``：进程内滑动窗口限流器
"""

from __future__ import annotations

import ipaddress
import os
import socket
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

#: 默认允许的下载目标域名后缀（各平台官网域名 + 常见媒体/CDN 域名）。
#: 匹配规则：目标 host 本身或其任意子域命中即可，例如 ``douyin.com``
#: 可放行 ``www.douyin.com``、``v3-web.douyinvod.com`` 等。
DEFAULT_DOWNLOAD_HOST_SUFFIXES = frozenset(
    {
        # 字节系：抖音/西瓜/皮皮虾/皮皮搞笑
        "douyin.com",
        "iesdouyin.com",
        "douyinvod.com",
        "douyinstatic.com",
        "douyinpic.com",
        "byteimg.com",
        "amemv.com",
        "snssdk.com",
        "pstatp.com",
        "toutiaoimg.com",
        "ixigua.com",
        "pipix.com",
        "ippzone.com",
        "pipigx.com",
        # 百度系：好看视频/度小视/全民小视频
        "hao222.com",
        "bdstatic.com",
        "bcebos.com",
        # 快手
        "kuaishou.com",
        "kwaicdn.com",
        "kwimgs.com",
        "yximgs.com",
        # B站
        "bilibili.com",
        "b23.tv",
        "hdslb.com",
        "bilivideo.com",
        "biliimg.com",
        # 小红书
        "xiaohongshu.com",
        "xhscdn.com",
        "xhslink.com",
        "xhslink.cn",
        # 微博/绿洲
        "weibo.com",
        "weibo.cn",
        "sinaimg.cn",
        "weibocdn.com",
        "sinajs.cn",
        # 腾讯系：微视/腾讯视频/全民K歌
        "qq.com",
        "gtimg.com",
        "gtimg.cn",
        "qpic.cn",
        "myqcloud.com",
        # 搜狐/央视
        "sohu.com",
        "sohucs.com",
        "cctv.com",
        "cntv.cn",
        # AcFun/虎牙/梨视频
        "acfun.cn",
        "huya.com",
        "huyavideo.com",
        "huyacdn.com",
        "pearvideo.com",
        # 美拍/六间房/新片场/逗拍/最右
        "meipai.com",
        "meipaimv.com",
        "6.cn",
        "xinpianchang.com",
        "qiniucdn.com",
        "qiniudns.com",
        "doupai.cc",
        "xiaochuankeji.cn",
        # TikTok/Instagram/Twitter(X)
        "tiktok.com",
        "tiktokcdn.com",
        "tiktokcdn-us.com",
        "tiktokcdn-cn.com",
        "tiktokv.com",
        "instagram.com",
        "cdninstagram.com",
        "fbcdn.net",
        "twitter.com",
        "x.com",
        "twimg.com",
    }
)

#: 通过环境变量追加允许的域名后缀（逗号分隔，不带前导点）
_ENV_ALLOW_HOSTS = "PARSE_VIDEO_DOWNLOAD_ALLOW_HOSTS"
#: 设为 1 时跳过域名白名单（仍保留内网/保留地址拦截），仅供自托管排查使用
_ENV_ALLOW_ALL = "PARSE_VIDEO_DOWNLOAD_ALLOW_ALL"


def _extra_host_suffixes() -> frozenset[str]:
    raw = os.getenv(_ENV_ALLOW_HOSTS, "")
    return frozenset(
        suffix.strip().lower().lstrip(".")
        for suffix in raw.split(",")
        if suffix.strip()
    )


def _allow_all_hosts() -> bool:
    return os.getenv(_ENV_ALLOW_ALL, "").strip().lower() in {"1", "true", "yes", "on"}


def host_allowed(host: str) -> bool:
    """判断 host 是否命中白名单（host 本身或任一父域命中即放行）。"""
    host = host.strip().lower().rstrip(".")
    if not host:
        return False
    allowed = DEFAULT_DOWNLOAD_HOST_SUFFIXES | _extra_host_suffixes()
    if host in allowed:
        return True
    return any(host.endswith("." + suffix) for suffix in allowed)


def public_ip_error(host: str) -> str | None:
    """解析 host；若指向内网/回环/链路本地等非公网地址，返回错误信息。"""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return f"域名解析失败: {host}"
    if not infos:
        return f"域名无法解析: {host}"
    for info in infos:
        ip = info[4][0].split("%")[0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            return f"目标地址不允许访问（内网/保留地址）: {ip}"
    return None


def validate_proxy_url(url: str) -> str | None:
    """校验下载代理目标 URL。

    返回 ``None`` 表示允许下载；否则返回可直接展示给用户的错误信息。
    """
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return "仅支持 http/https 下载链接"
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return "无效的下载链接"
    if not _allow_all_hosts() and not host_allowed(host):
        return (
            f"下载域名不在允许列表: {host}"
            "（如需放行请在服务端设置 PARSE_VIDEO_DOWNLOAD_ALLOW_HOSTS）"
        )
    return public_ip_error(host)


class RateLimiter:
    """按 key（通常是客户端 IP）统计的滑动窗口限流器。

    进程内实现，单机部署足够；``limit <= 0`` 表示不限流。
    """

    def __init__(self, limit: int, window: float = 60.0):
        self.limit = max(0, int(limit))
        self.window = max(1.0, float(window))
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._max_keys = 8192

    def allow(self, key: str) -> bool:
        """记录一次访问；未超过窗口上限返回 True，否则返回 False。"""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        self._prune_if_needed()
        return True

    def _prune_if_needed(self) -> None:
        """防止大量短命客户端 IP 撑爆内存。"""
        if len(self._hits) <= self._max_keys:
            return
        empty_keys = [key for key, hits in self._hits.items() if not hits]
        for key in empty_keys:
            del self._hits[key]

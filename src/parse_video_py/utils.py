import os
import re
from urllib.parse import parse_qs, urlparse

import httpx
from yarl import URL

# 匹配单个 URL
URL_REG = re.compile(r"http[s]?:\/\/[\w.-]+[\w\/-]*[\w.-]*\??[\w=&:\-\+\%.]*[/]*")

# 支持从一段文本中提取多个 URL
MULTI_URL_REG = re.compile(r"https?://[^\s<>\"']+")

# 平台域名映射（用于显示平台名）
PLATFORM_DOMAINS = {
    "douyin.com": "抖音",
    "iesdouyin.com": "抖音",
    "v.douyin.com": "抖音",
    "kuaishou.com": "快手",
    "v.kuaishou.com": "快手",
    "pipix.com": "皮皮虾",
    "h5.pipix.com": "皮皮虾",
    "weibo.com": "微博",
    "weibo.cn": "绿洲",
    "isee.weishi.qq.com": "微视",
    "share.xiaochuankeji.cn": "最右",
    "xspshare.baidu.com": "度小视",
    "ixigua.com": "西瓜视频",
    "v.ixigua.com": "西瓜视频",
    "pearvideo.com": "梨视频",
    "h5.pipigx.com": "皮皮搞笑",
    "huya.com": "虎牙",
    "v.huya.com": "虎牙",
    "acfun.cn": "AcFun",
    "www.acfun.cn": "AcFun",
    "doupai.cc": "逗拍",
    "meipai.com": "美拍",
    "kg.qq.com": "全民K歌",
    "6.cn": "六间房",
    "xinpianchang.com": "新片场",
    "haokan.baidu.com": "好看视频",
    "bilibili.com": "B站",
    "b23.tv": "B站",
    "xiaohongshu.com": "小红书",
    "xhslink.com": "小红书",
    "xhslink.cn": "小红书",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "t.co": "Twitter/X",
    "v.qq.com": "腾讯视频",
    "tv.sohu.com": "搜狐视频",
    "tv.cctv.com": "央视网",
    "tiktok.com": "TikTok",
    "vt.tiktok.com": "TikTok",
    "vm.tiktok.com": "TikTok",
    "instagram.com": "Instagram",
}


def detect_platform(url: str) -> str:
    """从 URL 中检测平台名称"""
    for domain, name in PLATFORM_DOMAINS.items():
        if domain in url:
            return name
    return "未知平台"


def extract_url(text: str) -> str | None:
    """从文本中提取第一个匹配的 URL"""
    match = URL_REG.search(text)
    return match.group() if match else None


def extract_all_urls(text: str) -> list[str]:
    """从一段文本中提取所有匹配的 URL"""
    matches = MULTI_URL_REG.findall(text)
    result = []
    for m in matches:
        # 清理尾部标点
        m = m.strip().rstrip(".,;:!?，。；：！？")
        if m:
            result.append(m)
    return result


def get_val_from_url_by_query_key(url: str, query_key: str) -> str:
    """
    从url的query参数中解析出query_key对应的值
    """
    url_res = urlparse(url)
    url_query = parse_qs(url_res.query, keep_blank_values=True)
    try:
        query_val = url_query[query_key][0]
    except KeyError:
        raise KeyError(f"url中不存在query参数: {query_key}")
    if len(query_val) == 0:
        raise ValueError(f"url中query参数值长度为0: {query_key}")
    return url_query[query_key][0]


def create_async_client(**kwargs) -> httpx.AsyncClient:
    """创建 httpx.AsyncClient，自动注入代理配置。"""
    proxy = os.getenv("PARSE_VIDEO_PROXY")
    if proxy:
        kwargs["proxy"] = proxy

    # 仅当显式设置了 PARSE_VIDEO_TIMEOUT 环境变量时才注入超时
    timeout_env = os.getenv("PARSE_VIDEO_TIMEOUT")
    if timeout_env and "timeout" not in kwargs:
        try:
            kwargs["timeout"] = int(timeout_env)
        except ValueError:
            pass

    return httpx.AsyncClient(**kwargs)



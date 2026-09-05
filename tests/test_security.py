import socket
import time

from parse_video_py.security import (
    DEFAULT_DOWNLOAD_HOST_SUFFIXES,
    RateLimiter,
    validate_proxy_url,
)


def _patch_public_dns(monkeypatch):
    """让任意域名解析到公网 IP，避免测试依赖真实 DNS。"""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def _clear_allow_env(monkeypatch):
    monkeypatch.delenv("PARSE_VIDEO_DOWNLOAD_ALLOW_HOSTS", raising=False)
    monkeypatch.delenv("PARSE_VIDEO_DOWNLOAD_ALLOW_ALL", raising=False)


def test_default_allowlist_contains_core_platform_domains():
    for suffix in ("douyin.com", "kuaishou.com", "bilibili.com", "xhscdn.com"):
        assert suffix in DEFAULT_DOWNLOAD_HOST_SUFFIXES


def test_rejects_non_http_scheme():
    assert "仅支持 http/https" in validate_proxy_url("ftp://example.com/video.mp4")
    assert "仅支持 http/https" in validate_proxy_url("file:///etc/passwd")


def test_rejects_missing_host():
    assert validate_proxy_url("http:///path") is not None


def test_rejects_non_allowlisted_public_host(monkeypatch):
    _clear_allow_env(monkeypatch)
    error = validate_proxy_url("https://evil.example.net/steal.mp4")
    assert error is not None
    assert "不在允许列表" in error


def test_rejects_private_ip_even_when_host_added_to_allowlist(monkeypatch):
    monkeypatch.setenv("PARSE_VIDEO_DOWNLOAD_ALLOW_HOSTS", "127.0.0.1,::1")
    error = validate_proxy_url("http://127.0.0.1:8000/admin")
    assert error is not None
    assert "不允许访问" in error

    error = validate_proxy_url("http://[::1]:8080/admin")
    assert error is not None
    assert "不允许访问" in error


def test_allows_public_allowlisted_host_with_valid_dns(monkeypatch):
    _clear_allow_env(monkeypatch)
    _patch_public_dns(monkeypatch)

    assert (
        validate_proxy_url("https://www.douyin.com/aweme/v1/play/?video_id=x") is None
    )
    assert validate_proxy_url("https://sns-video-bd.xhscdn.com/stream/1.mp4") is None


def test_allow_all_flag_still_blocks_private_ip(monkeypatch):
    monkeypatch.setenv("PARSE_VIDEO_DOWNLOAD_ALLOW_ALL", "1")

    error = validate_proxy_url("http://192.168.1.10/config.json")
    assert error is not None
    assert "不允许访问" in error

    error = validate_proxy_url("http://169.254.169.254/latest/meta-data/")
    assert error is not None
    assert "不允许访问" in error


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(limit=3, window=60.0)

    assert limiter.allow("client-1")
    assert limiter.allow("client-1")
    assert limiter.allow("client-1")
    assert not limiter.allow("client-1")
    # 其他客户端不受影响
    assert limiter.allow("client-2")


def test_rate_limiter_resets_after_window(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    limiter = RateLimiter(limit=1, window=60.0)

    assert limiter.allow("client-1")
    assert not limiter.allow("client-1")
    clock["now"] += 60.0
    assert limiter.allow("client-1")


def test_rate_limiter_disabled_when_limit_is_zero():
    limiter = RateLimiter(limit=0, window=60.0)
    for _ in range(10):
        assert limiter.allow("client-1")

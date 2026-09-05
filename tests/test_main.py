from fastapi.testclient import TestClient

from parse_video_py.web import app

client = TestClient(app)


def test_share_url_parse_returns_400_when_no_url_found():
    response = client.get("/video/share/url/parse", params={"url": "这不是链接"})

    assert response.status_code == 200
    assert response.json() == {"code": 400, "msg": "未检测到有效的分享链接"}


def test_share_url_parse_returns_400_for_empty_string():
    response = client.get("/video/share/url/parse", params={"url": ""})

    assert response.status_code == 200
    assert response.json() == {"code": 400, "msg": "未检测到有效的分享链接"}


def test_share_url_parse_returns_400_for_partial_url_without_scheme():
    response = client.get(
        "/video/share/url/parse", params={"url": "example.com/video/123"}
    )

    assert response.status_code == 200
    assert response.json() == {"code": 400, "msg": "未检测到有效的分享链接"}


def test_share_url_parse_returns_422_when_url_param_missing():
    response = client.get("/video/share/url/parse")

    assert response.status_code == 422


def test_cors_preflight_allows_github_pages_origin():
    response = client.options(
        "/video/share/url/parse/batch",
        headers={
            "Origin": "https://aolined.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_download_direct_rejects_non_allowlisted_host():
    response = client.get(
        "/video/download/direct", params={"url": "http://example.com/secret.mp4"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 400
    assert "不在允许列表" in body["msg"]


def test_download_direct_rejects_private_ip_literal():
    response = client.get(
        "/video/download/direct", params={"url": "http://127.0.0.1:8000/secret"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 400


def test_download_direct_rejects_non_http_scheme():
    response = client.get(
        "/video/download/direct", params={"url": "file:///etc/passwd"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 400
    assert "仅支持 http/https" in body["msg"]

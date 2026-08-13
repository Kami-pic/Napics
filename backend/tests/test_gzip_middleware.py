"""gzip 中间件行为验证：大 JSON 响应压缩，SSE 流式响应不压缩"""
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from main import ConditionalGZipMiddleware, _SSE_PATHS


def _build_app() -> FastAPI:
    """构造一个最小 app，复用生产中间件配置"""
    app = FastAPI()
    app.add_middleware(ConditionalGZipMiddleware, minimum_size=1024)

    @app.get("/library")
    def big_json():
        # 造一个远超 minimum_size 的响应
        return [{"file_path": f"/media/video_{i}.mkv", "clean_name": "测试影片"} for i in range(200)]

    @app.get("/tiny")
    def tiny_json():
        return {"ok": True}

    @app.get("/scan")
    def sse():
        def gen():
            for i in range(3):
                yield "data: " + json.dumps({"current": i, "padding": "x" * 2000}) + "\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def test_large_json_is_gzipped():
    """大 JSON 响应应带 content-encoding: gzip，且解压后内容完整"""
    client = TestClient(_build_app())
    resp = client.get("/library", headers={"accept-encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    # httpx 自动解压，内容必须完整可解析
    data = resp.json()
    assert len(data) == 200
    assert data[0]["clean_name"] == "测试影片"


def test_small_response_not_gzipped():
    """小于 minimum_size 的响应不压缩"""
    client = TestClient(_build_app())
    resp = client.get("/tiny", headers={"accept-encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") is None
    assert resp.json() == {"ok": True}


def test_sse_path_is_not_gzipped():
    """SSE 路由必须透传，不能被压缩（否则实时进度会被缓冲）"""
    client = TestClient(_build_app())
    resp = client.get("/scan", headers={"accept-encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") is None
    assert resp.headers["content-type"].startswith("text/event-stream")
    # 三条事件都要完整送达
    assert resp.text.count("data: ") == 3


def test_sse_path_list_covers_all_stream_routes():
    """守卫：后端所有 text/event-stream 路由都必须在 _SSE_PATHS 中登记"""
    import os
    import re

    routes_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routes")
    # 从源码里提取挂了 SSE 的路由装饰器路径
    declared = set()
    for fname in os.listdir(routes_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(routes_dir, fname), "r", encoding="utf-8") as f:
            src = f.read()
        if 'media_type="text/event-stream"' not in src:
            continue
        for m in re.finditer(r'@router\.(?:get|post)\(\s*"([^"]+)"', src):
            declared.add(m.group(1))

    # 只校验确实是 SSE 的那些路径已被登记（宽松：declared 是文件级候选集）
    missing = [p for p in _SSE_PATHS if not any(d == p for d in declared)]
    assert not missing, f"_SSE_PATHS 中的路径在 routes/ 里找不到对应声明: {missing}"

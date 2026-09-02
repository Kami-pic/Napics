"""网盘搜索全链路测试 — 测试 PanSearchService 聚合搜索。

用法：
  cd backend
  python test_pan_search.py "流浪地球"
  python test_pan_search.py "权力的游戏" tv

也可以启动后端后直接浏览器访问：
  http://localhost:8000/search/pan?keyword=流浪地球
"""

import sys
import json
import asyncio

from pan_search_service import PanSearchService

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "流浪地球"
    media_type = sys.argv[2] if len(sys.argv) > 2 else ""

    print(f"\n🔍 网盘搜索: {keyword}" + (f" (类型: {media_type})" if media_type else ""))
    print("=" * 60)

    # 默认只启用 pansearch（国内可直连），rrdynb/ddys 需要 Playwright
    service = PanSearchService(
        search_sources={"pansearch": True, "rrdynb": False, "ddys": False, "pansou": False},
    )

    response = service.search_sync(keyword, media_type=media_type)

    # 打印各源状态
    print("\n📡 搜索源状态:")
    for s in response.source_statuses:
        icon = "✅" if s.status == "success" else "❌" if s.status == "failed" else "⭕"
        print(f"  {icon} {s.name}: {s.status} ({s.count} 条)" +
              (f" — {s.error}" if s.error else ""))

    print(f"\n📊 总计: {response.total} 条结果")

    if not response.results:
        print("❌ 无结果")
        return

    # 按分组打印
    for pan_type, items in response.groups.items():
        print(f"\n── {pan_type} ({len(items)} 条) ──")
        for i, r in enumerate(items, 1):
            mounted = "✅" if r.mounted else "🔒未挂载"
            complete = "整季" if r.is_complete else "碎片"
            print(f"  [{i}] {r.clean_title or r.title}")
            print(f"      链接: {r.share_url}")
            print(f"      提取码: {r.password or '(无)'}")
            print(f"      分辨率: {r.resolution} | {complete} | {mounted}")
            print(f"      来源: {r.source}")

    # JSON 输出
    print("\n" + "=" * 60)
    print("📋 JSON:")
    print(json.dumps(response.dict(), ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    main()

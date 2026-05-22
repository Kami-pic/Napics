"""RrdynbScraper 实测脚本 — 搜索一个关键词，打印结果。

用法：
  cd backend
  python test_rrdynb.py "流浪地球"
  python test_rrdynb.py "权力的游戏"
"""

import sys
import json

from pan_scraper_rrdynb import RrdynbScraper


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "流浪地球"
    print(f"\n🔍 搜索关键词: {keyword}")
    print("=" * 60)

    scraper = RrdynbScraper()
    results = scraper.search(keyword)

    if not results:
        print("❌ 无结果（可能站点结构变了，或者关键词没命中）")
        return

    print(f"✅ 找到 {len(results)} 条网盘链接:\n")

    for i, r in enumerate(results, 1):
        print(f"  [{i}] {r.clean_title or r.title}")
        print(f"      网盘: {r.pan_type.value}")
        print(f"      链接: {r.share_url}")
        print(f"      提取码: {r.password or '(无)'}")
        print(f"      分辨率: {r.resolution}")
        print(f"      整季: {'是' if r.is_complete else '否(碎片集)'}")
        print(f"      来源: {r.source}")
        print()

    # 也输出 JSON 格式方便检查
    print("=" * 60)
    print("📋 JSON 格式:")
    json_data = [r.dict() for r in results]
    print(json.dumps(json_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

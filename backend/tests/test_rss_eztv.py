"""EZTV RSS 源测试：解析逻辑验证（模拟数据，不请求网络）。"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rss_source_eztv import EZTVRSSSource


# 模拟 EZTV RSS XML（真实格式）
MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torrent="http://xmlns.ezrss.it/0.1/">
  <channel>
    <title>EZTV RSS</title>
    <item>
      <title>The Boys S05E03 1080p WEB-DL x265 HEVC-GROUP</title>
      <link>https://eztv.re/ep_123456</link>
      <torrent:magnetURI>magnet:?xt=urn:btih:AABBCCDDEE11223344556677889900AABBCCDDEE&amp;dn=The+Boys+S05E03</torrent:magnetURI>
      <torrent:infoHash>AABBCCDDEE11223344556677889900AABBCCDDEE</torrent:infoHash>
      <torrent:contentLength>2147483648</torrent:contentLength>
      <torrent:seeds>150</torrent:seeds>
      <pubDate>Fri, 04 Jul 2025 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>The Boys S05E03 720p WEB-DL x264-SMALL</title>
      <link>magnet:?xt=urn:btih:1122334455667788990011223344556677889900&amp;dn=The+Boys+S05E03+720p</link>
      <torrent:seeds>80</torrent:seeds>
      <torrent:contentLength>1073741824</torrent:contentLength>
      <pubDate>Fri, 04 Jul 2025 11:30:00 +0000</pubDate>
    </item>
    <item>
      <title>Some Other Show S01E01</title>
      <link>https://eztv.re/ep_999</link>
    </item>
  </channel>
</rss>"""


def test_parse_rss():
    """测试 RSS XML 解析"""
    src = EZTVRSSSource()
    items = src._parse_rss_xml(MOCK_RSS_XML)

    # 第三条没有磁力链接，应该被跳过
    assert len(items) == 2, f"期望 2 条，实际 {len(items)}"

    # 第一条：完整信息
    item1 = items[0]
    assert item1.title == "The Boys S05E03 1080p WEB-DL x265 HEVC-GROUP"
    assert "AABBCCDDEE11223344556677889900AABBCCDDEE" in item1.download_url
    assert item1.info_hash == "AABBCCDDEE11223344556677889900AABBCCDDEE"
    assert item1.size_gb == 2.0  # 2GB
    assert item1.seeders == 150
    assert item1.episode == 3
    assert item1.season == 5
    assert item1.source_name == "eztv"
    assert "1080p" in item1.resolution or "1080p" in item1.quality_tag
    print(f"  [PASS] 完整信息解析: {item1.title}")

    # 第二条：磁力链接在 link 中
    item2 = items[1]
    assert item2.download_url.startswith("magnet:")
    assert item2.info_hash == "1122334455667788990011223344556677889900"
    assert item2.size_gb == 1.0  # 1GB
    assert item2.seeders == 80
    assert item2.episode == 3
    assert item2.season == 5
    print(f"  [PASS] link 磁力链接解析: {item2.title}")

    print("[PASS] test_parse_rss")


def test_build_keywords():
    """测试搜索词构造"""
    from subscriber import Subscription
    src = EZTVRSSSource()

    # 有 IMDB ID 时不需要关键词
    sub = Subscription(
        title="黑袍纠察队",
        type="tv",
        imdb_id="tt1190634",
        aliases={"cn": ["黑袍纠察队"], "en": ["The Boys"], "original": []},
    )
    kws = src._build_search_keywords(sub)
    # 英文名优先
    assert kws[0] == "The Boys", f"期望 'The Boys'，实际 '{kws[0]}'"
    print(f"  [PASS] 英文名优先: {kws}")

    # 自定义搜索词覆盖
    sub2 = Subscription(title="测试", search_keyword="custom keyword")
    kws2 = src._build_search_keywords(sub2)
    assert kws2 == ["custom keyword"]
    print(f"  [PASS] 自定义搜索词: {kws2}")

    print("[PASS] test_build_keywords")


if __name__ == "__main__":
    print("=" * 50)
    print("EZTV RSS 源测试")
    print("=" * 50)
    test_parse_rss()
    test_build_keywords()
    print("\n✅ EZTV RSS 源测试全部通过")

"""Phase 4a/4b 测试：新 RSS 源 + 通知服务 + 搜索缓存 + 速率限制。"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# ── Phase 4a: RSS 源基础测试 ──

class TestDMHYRSSSource:
    """动漫花园 RSS 源测试"""

    def test_init(self):
        from rss_source_dmhy import DMHYRSSSource
        source = DMHYRSSSource(proxy="http://127.0.0.1:7897")
        assert source.name == "dmhy"
        assert source.display_name == "动漫花园"

    def test_build_search_keywords(self):
        from rss_source_dmhy import DMHYRSSSource
        source = DMHYRSSSource()
        sub = MagicMock()
        sub.search_keyword = ""
        sub.title = "葬送的芙莉莲"
        sub.aliases = {"cn": ["葬送的芙莉莲"], "en": ["Frieren"], "original": ["葬送のフリーレン"]}
        keywords = source._build_search_keywords(sub)
        assert "葬送的芙莉莲" in keywords
        assert "葬送のフリーレン" in keywords

    def test_build_search_keywords_custom(self):
        from rss_source_dmhy import DMHYRSSSource
        source = DMHYRSSSource()
        sub = MagicMock()
        sub.search_keyword = "自定义搜索词"
        keywords = source._build_search_keywords(sub)
        assert keywords == ["自定义搜索词"]

    def test_parse_rss_xml(self):
        from rss_source_dmhy import DMHYRSSSource
        source = DMHYRSSSource()
        xml = """<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
        <channel>
        <item>
            <title>[字幕组] 葬送的芙莉莲 - 01 [1080p]</title>
            <link>https://share.dmhy.org/topics/view/123</link>
            <enclosure url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12" length="1073741824"/>
            <pubDate>Wed, 01 Jan 2025 00:00:00 +0800</pubDate>
        </item>
        </channel>
        </rss>"""
        items = source._parse_rss_xml(xml)
        assert len(items) == 1
        assert items[0].title == "[字幕组] 葬送的芙莉莲 - 01 [1080p]"
        assert items[0].info_hash == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
        assert items[0].source_name == "dmhy"
        assert items[0].episode == 1
        assert items[0].size_gb == pytest.approx(1.0, abs=0.01)


class TestACGRipRSSSource:
    """ACG.RIP RSS 源测试"""

    def test_init(self):
        from rss_source_acgrip import ACGRipRSSSource
        source = ACGRipRSSSource()
        assert source.name == "acgrip"
        assert source.display_name == "ACG.RIP"

    def test_build_search_keywords(self):
        from rss_source_acgrip import ACGRipRSSSource
        source = ACGRipRSSSource()
        sub = MagicMock()
        sub.search_keyword = ""
        sub.title = "进击的巨人"
        sub.aliases = {"cn": ["进击的巨人"], "original": ["進撃の巨人"]}
        keywords = source._build_search_keywords(sub)
        assert "进击的巨人" in keywords

    def test_parse_rss_xml(self):
        from rss_source_acgrip import ACGRipRSSSource
        source = ACGRipRSSSource()
        xml = """<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
        <channel>
        <item>
            <title>[字幕组] 进击的巨人 - 01 [1080p]</title>
            <link>https://acg.rip/t/12345</link>
            <enclosure url="https://acg.rip/t/12345.torrent" length="536870912"/>
            <pubDate>Wed, 01 Jan 2025 00:00:00 +0000</pubDate>
        </item>
        </channel>
        </rss>"""
        items = source._parse_rss_xml(xml)
        assert len(items) == 1
        assert items[0].source_name == "acgrip"
        assert items[0].download_url == "https://acg.rip/t/12345.torrent"
        assert items[0].info_hash == ""  # ACG.RIP 没有 infohash
        assert items[0].size_gb == pytest.approx(0.5, abs=0.01)


class TestBangumiMoeRSSSource:
    """Bangumi Moe RSS 源测试"""

    def test_init(self):
        from rss_source_bangumi_moe import BangumiMoeRSSSource
        source = BangumiMoeRSSSource()
        assert source.name == "bangumi_moe"
        assert source.display_name == "Bangumi Moe"

    def test_parse_torrent(self):
        from rss_source_bangumi_moe import BangumiMoeRSSSource
        source = BangumiMoeRSSSource()
        torrent = {
            "title": "[字幕组] 鬼灭之刃 - 01 [1080p]",
            "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
            "size": 1073741824,
            "seeders": 50,
        }
        item = source._parse_torrent(torrent)
        assert item is not None
        assert item.title == "[字幕组] 鬼灭之刃 - 01 [1080p]"
        assert item.info_hash == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
        assert item.seeders == 50
        assert item.size_gb == pytest.approx(1.0, abs=0.01)

    def test_parse_torrent_string_size(self):
        from rss_source_bangumi_moe import BangumiMoeRSSSource
        source = BangumiMoeRSSSource()
        torrent = {
            "title": "Test",
            "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
            "size": "118.6 GB",
        }
        item = source._parse_torrent(torrent)
        assert item is not None
        assert item.size_gb == pytest.approx(118.6, abs=0.1)

    def test_parse_torrent_no_hash(self):
        from rss_source_bangumi_moe import BangumiMoeRSSSource
        source = BangumiMoeRSSSource()
        torrent = {"title": "Test", "_id": "abc123"}
        item = source._parse_torrent(torrent)
        assert item is not None
        assert "abc123" in item.download_url


class TestYTSRSSSource:
    """YTS RSS 源测试"""

    def test_init(self):
        from rss_source_yts import YTSRSSSource
        source = YTSRSSSource(proxy="http://127.0.0.1:7897")
        assert source.name == "yts"
        assert source.display_name == "YTS"

    def test_build_search_keywords(self):
        from rss_source_yts import YTSRSSSource
        source = YTSRSSSource()
        sub = MagicMock()
        sub.search_keyword = ""
        sub.title = "Dune Part Two"
        sub.aliases = {"en": ["Dune Part Two"], "cn": ["沙丘2"]}
        keywords = source._build_search_keywords(sub)
        assert "Dune Part Two" in keywords

    def test_parse_movie(self):
        from rss_source_yts import YTSRSSSource
        source = YTSRSSSource()
        movie = {
            "title": "Dune Part Two",
            "title_long": "Dune: Part Two (2024)",
            "year": 2024,
            "url": "https://yts.mx/movies/dune-part-two-2024",
            "torrents": [
                {
                    "hash": "ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                    "quality": "1080p",
                    "video_codec": "x265",
                    "type": "bluray",
                    "size_bytes": 2147483648,
                    "seeds": 100,
                    "peers": 50,
                },
            ],
        }
        items = source._parse_movie(movie)
        assert len(items) == 1
        assert "Dune" in items[0].title
        assert items[0].info_hash == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
        assert items[0].seeders == 100
        assert items[0].size_gb == pytest.approx(2.0, abs=0.01)


# ── Phase 4b: 通知服务测试 ──

class TestNotificationService:
    """通知服务测试"""

    def _make_sub_manager(self):
        """创建一个 mock SubscriptionManager"""
        from subscriber import Subscription
        sub = Subscription(id="test-1", title="测试订阅")
        mgr = MagicMock()
        mgr.get.return_value = sub
        mgr.get_all.return_value = [sub]
        return mgr, sub

    def test_add_notification(self):
        from notification_service import add_notification
        mgr, sub = self._make_sub_manager()
        add_notification(mgr, "test-1", "download_complete", "下载完成: E01")
        mgr.append_notification.assert_called_once()
        call_args = mgr.append_notification.call_args
        assert call_args.args[0] == "test-1"
        assert call_args.args[1].type == "download_complete"

    def test_add_search_log(self):
        from notification_service import add_search_log
        mgr, sub = self._make_sub_manager()
        add_search_log(
            mgr, "test-1", channel="rss", total=10, matched=3,
            best_quality="1080p WEB-DL", sources_ok=["mikan", "nyaa"],
            summary="搜到 3 条",
        )
        mgr.append_search_log.assert_called_once()
        call_args = mgr.append_search_log.call_args
        log = call_args.args[1]
        assert log.channel == "rss"
        assert log.total == 10
        assert log.matched == 3

    def test_get_unread_count(self):
        from notification_service import get_unread_count
        from subscriber import Subscription, NotificationEntry
        sub = Subscription(
            id="test-1", title="测试",
            notifications=[
                NotificationEntry(type="download_complete", message="test", read=False),
                NotificationEntry(type="download_complete", message="test2", read=True),
            ],
        )
        mgr = MagicMock()
        mgr.get_all.return_value = [sub]
        assert get_unread_count(mgr) == 1

    def test_mark_notifications_read(self):
        from notification_service import mark_notifications_read
        from subscriber import Subscription, NotificationEntry
        sub = Subscription(
            id="test-1", title="测试",
            notifications=[
                NotificationEntry(type="download_complete", message="test", read=False),
            ],
        )
        mgr = MagicMock()
        mgr.get.return_value = sub
        mark_notifications_read(mgr, "test-1")
        call_args = mgr.update.call_args
        notifications = call_args[0][1]["notifications"]
        assert all(n["read"] for n in notifications)


# ── Phase 4b: 搜索缓存测试 ──

class TestSearchResultCache:
    """搜索结果缓存测试"""

    def test_set_and_get(self):
        from rss_engine import SearchResultCache
        from rss_source_base import RSSItem
        cache = SearchResultCache(ttl_seconds=60)
        items = [RSSItem(title="test", source_name="nyaa")]
        cache.set("nyaa", "keyword1", items)
        result = cache.get("nyaa", "keyword1")
        assert result is not None
        assert len(result) == 1

    def test_cache_miss(self):
        from rss_engine import SearchResultCache
        cache = SearchResultCache(ttl_seconds=60)
        assert cache.get("nyaa", "nonexistent") is None

    def test_empty_not_cached(self):
        from rss_engine import SearchResultCache
        cache = SearchResultCache(ttl_seconds=60)
        cache.set("nyaa", "empty", [])
        assert cache.get("nyaa", "empty") is None

    def test_ttl_expiry(self):
        import time
        from rss_engine import SearchResultCache
        from rss_source_base import RSSItem
        cache = SearchResultCache(ttl_seconds=1)
        items = [RSSItem(title="test", source_name="nyaa")]
        cache.set("nyaa", "keyword1", items)
        time.sleep(1.1)
        assert cache.get("nyaa", "keyword1") is None


# ── Phase 4b: 速率限制测试 ──

class TestRateLimiter:
    """全局速率限制器测试"""

    def test_acquire_within_limit(self):
        from rss_engine import RateLimiter
        limiter = RateLimiter(max_per_minute=3)
        assert limiter.acquire("nyaa") is True
        assert limiter.acquire("nyaa") is True
        assert limiter.acquire("nyaa") is True
        assert limiter.acquire("nyaa") is False  # 超过限制

    def test_different_sources_independent(self):
        from rss_engine import RateLimiter
        limiter = RateLimiter(max_per_minute=2)
        assert limiter.acquire("nyaa") is True
        assert limiter.acquire("nyaa") is True
        assert limiter.acquire("nyaa") is False
        # 不同源不受影响
        assert limiter.acquire("mikan") is True


# ── 数据模型兼容性测试 ──

class TestSubscriptionModelCompat:
    """Subscription 模型新增字段兼容性测试"""

    def test_new_fields_default(self):
        from subscriber import Subscription
        sub = Subscription(id="test", title="测试")
        assert sub.search_logs == []
        assert sub.notifications == []

    def test_old_data_compat(self):
        """旧数据（无新字段）加载不报错"""
        from subscriber import Subscription
        old_data = {"id": "test", "title": "测试", "year": "2024"}
        sub = Subscription(**old_data)
        assert sub.search_logs == []
        assert sub.notifications == []

    def test_search_log_entry(self):
        from subscriber import SearchLogEntry
        entry = SearchLogEntry(
            timestamp="2025-01-01 00:00:00",
            channel="rss", total=10, matched=3,
            sources_ok=["mikan"], sources_fail=["nyaa"],
        )
        d = entry.model_dump()
        assert d["channel"] == "rss"
        assert d["total"] == 10

    def test_notification_entry(self):
        from subscriber import NotificationEntry
        entry = NotificationEntry(
            timestamp="2025-01-01 00:00:00",
            type="download_complete",
            message="下载完成",
            read=False,
        )
        d = entry.model_dump()
        assert d["read"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
